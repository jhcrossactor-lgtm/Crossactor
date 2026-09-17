"""OpenAI 画像編集API（ChatGPT Image / gpt-image 系）アダプタ。

エンドポイント: POST https://api.openai.com/v1/images/edits  (multipart/form-data)
  image[]  1枚目が編集対象、2枚目以降が参照画像（最大16枚）
  prompt   編集指示
  size     "WIDTHxHEIGHT"。幅・高さとも16の倍数、アスペクト比は1:3〜3:1
  quality  low / medium / high / xhigh / max （2.5系は xhigh・max も可）
レスポンスは常に base64（data[0].b64_json）。response_format は送ってはいけない（400）。
input_fidelity も送らない — gpt-image-2 以降は入力を常に高忠実度で扱うため、
このパイプラインの「建物は変更禁止」という要件はモデル既定の挙動で満たされる。

認証は2通り:
  auth: bearer  … 自分で Authorization ヘッダを付ける（ローカル実行の既定）
  auth: proxy   … ヘッダを付けない。クラウド環境の API credentials 側で
                  エージェントプロキシが Authorization を注入する
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from ..util import RunLogger, require_api_key
from .base import ImageProvider, mime_of

# size の制約（幅・高さとも16の倍数、総画素数、最大辺）
SIZE_STEP = 16
MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE = 3840


def validate_size(size: str) -> list[str]:
    """size 文字列を検証し、問題があればその一覧を返す（空なら問題なし）。"""
    problems: list[str] = []
    try:
        width_text, _, height_text = size.lower().partition("x")
        width, height = int(width_text), int(height_text)
    except ValueError:
        return [f"size の形式が不正: {size!r}（例: 2048x1152）"]

    if width % SIZE_STEP or height % SIZE_STEP:
        problems.append(f"幅・高さは{SIZE_STEP}の倍数である必要がある（{width}x{height}）")
    if max(width, height) > MAX_EDGE:
        problems.append(f"最大辺は{MAX_EDGE}px まで（{max(width, height)}px）")
    pixels = width * height
    if not (MIN_PIXELS <= pixels <= MAX_PIXELS):
        problems.append(f"総画素数は{MIN_PIXELS}〜{MAX_PIXELS}の範囲（{pixels}）")
    ratio = width / height if height else 0
    if not (1 / 3 <= ratio <= 3):
        problems.append(f"アスペクト比は1:3〜3:1の範囲（{ratio:.2f}:1）")
    return problems


def explain_http_error(status: int, body: str) -> str:
    """よくある失敗を日本語で言い切る。"""
    hints = {
        401: "APIキーが無効か未設定。.env の OPENAI_API_KEY を確認すること。",
        403: "このキー／組織でこのモデルが使えない。組織の本人確認が済んでいるか確認すること。",
        404: "モデル名かエンドポイントが違う。config.yaml の image.model を確認すること。",
        429: "レート上限か残高不足。時間を置くか課金設定を確認すること。",
        500: "OpenAI側の一時障害。リトライで解消することが多い。",
        503: "OpenAI側の一時障害。リトライで解消することが多い。",
    }
    hint = hints.get(status, "")
    if "response_format" in body:
        hint = "response_format は gpt-image 系では送れない（出力は常にbase64）。"
    if "input_fidelity" in body:
        hint = "input_fidelity は gpt-image-2 以降では送れない（常に高忠実度で処理される）。"
    return f"HTTP {status}: {body[:600]}" + (f"\n→ {hint}" if hint else "")


class ProxyBlockedError(RuntimeError):
    """エージェントプロキシが api.openai.com への接続を拒否した。"""


def post_images_edit(
    endpoint: str,
    headers: dict[str, str],
    data: dict[str, str],
    images: list[Path],
    timeout_sec: int,
) -> dict:
    """multipart で /v1/images/edits を叩き、JSONを返す。"""
    handles = []
    try:
        files = []
        for path in images:
            fh = open(path, "rb")
            handles.append(fh)
            files.append(("image[]", (path.name, fh, mime_of(path))))
        try:
            resp = requests.post(endpoint, headers=headers, data=data,
                                 files=files, timeout=timeout_sec)
        except requests.exceptions.ProxyError as exc:
            raise ProxyBlockedError(
                "エージェントプロキシが api.openai.com への接続を拒否した（egressポリシー）。"
                "クラウド環境のネットワーク設定でこのホストを許可するか、ローカルで実行すること。"
            ) from exc
        if resp.status_code >= 400:
            raise RuntimeError(explain_http_error(resp.status_code, resp.text))
        return resp.json()
    finally:
        for fh in handles:
            fh.close()


class OpenAIImageProvider(ImageProvider):
    name = "openai"

    def __init__(
        self,
        model: str,
        size: str,
        endpoint: str = "https://api.openai.com/v1/images/edits",
        quality: str = "high",
        api_key_env: str = "OPENAI_API_KEY",
        auth: str = "bearer",
        timeout_sec: int = 600,
        max_retries: int = 3,
        output_format: str = "png",
        **_: object,
    ) -> None:
        self.model = model
        self.size = size
        self.endpoint = endpoint
        self.quality = quality
        self.api_key_env = api_key_env
        self.auth = auth
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.output_format = output_format

    def headers(self) -> dict[str, str]:
        """auth: proxy のときは Authorization を付けない（プロキシが注入する）。"""
        if self.auth == "proxy":
            return {}
        return {"Authorization": f"Bearer {require_api_key(self.api_key_env)}"}

    def form_data(self, prompt: str) -> dict[str, str]:
        data = {"model": self.model, "prompt": prompt, "size": self.size, "n": "1"}
        if self.quality:
            data["quality"] = self.quality
        if self.output_format:
            data["output_format"] = self.output_format
        return data

    def edit(self, prompt, images, dst, logger: RunLogger, cut_id: str) -> Path:
        problems = validate_size(self.size)
        if problems:
            raise SystemExit("config.yaml の image.size が不正:\n  - " + "\n  - ".join(problems))

        dst.parent.mkdir(parents=True, exist_ok=True)
        headers = self.headers()
        data = self.form_data(prompt)

        logger.log(
            f"cut{cut_id} 画像編集を依頼 model={self.model} size={self.size} "
            f"quality={self.quality} auth={self.auth} images={[p.name for p in images]}",
            cut=cut_id, stage="1", model=self.model, size=self.size, quality=self.quality,
            auth=self.auth, images=[str(p) for p in images],
        )

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                started = time.time()
                payload = post_images_edit(self.endpoint, headers, data, images, self.timeout_sec)
                dst.write_bytes(base64.b64decode(payload["data"][0]["b64_json"]))
                usage = payload.get("usage") or {}
                logger.log(
                    f"cut{cut_id} 画像生成OK {time.time() - started:.1f}秒 -> {dst}",
                    cut=cut_id, stage="1", out=str(dst), usage=usage,
                )
                return dst
            except ProxyBlockedError:
                raise  # 到達できない以上リトライしても無駄
            except Exception as exc:
                last_error = exc
                logger.log(f"cut{cut_id} 画像生成 失敗 (試行{attempt}/{self.max_retries}): {exc}",
                           cut=cut_id, stage="1", error=str(exc))
                if attempt < self.max_retries:
                    time.sleep(5 * attempt)
        raise RuntimeError(f"cut{cut_id} 画像生成に失敗: {last_error}")
