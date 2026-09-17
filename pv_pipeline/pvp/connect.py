"""`python run.py connect` — 画像API・動画APIとの疎通確認。

キーの有無 → ホストへの到達性 → モデルの利用可否 → （任意で）実際の1枚編集、
の順に切り分けて、どこで止まっているかを言い切る。
片方が落ちても、もう片方のチェックは最後まで走らせる。
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .providers.openai_image import (
    ProxyBlockedError,
    explain_http_error,
    post_images_edit,
    validate_size,
)
from .util import Project, RunLogger

OK = "OK "
NG = "NG "
WARN = "-- "


def _models_endpoint(edit_endpoint: str) -> str:
    parts = urlsplit(edit_endpoint)
    return f"{parts.scheme}://{parts.netloc}/v1/models"


def _smoke_image(project: Project) -> list[Path]:
    """疎通確認用の小さな画像を作る。"""
    from PIL import Image

    work = project.log_dir / "connect"
    work.mkdir(parents=True, exist_ok=True)
    target = work / "smoke_input.png"
    Image.new("RGB", (1024, 576), (90, 120, 160)).save(target)
    return [target]


def check_image(project: Project, logger: RunLogger, smoke: bool = False) -> int:
    """画像API（ChatGPT Image）を見る。返り値は未解決件数。"""
    section = dict(project.config.get("image") or {})
    provider = section.get("provider", "openai")
    endpoint = section.get("endpoint", "https://api.openai.com/v1/images/edits")
    model = section.get("model", "")
    size = section.get("size", "")
    quality = section.get("quality", "high")
    auth = section.get("auth", "bearer")
    key_env = section.get("api_key_env", "OPENAI_API_KEY")
    timeout = int(section.get("timeout_sec", 600))
    host = urlsplit(endpoint).netloc

    print("=" * 64)
    print(" 画像API 連携チェック（ChatGPT Image）")
    print("=" * 64)
    print(f"  provider : {provider}")
    print(f"  endpoint : {endpoint}")
    print(f"  model    : {model}")
    print(f"  size     : {size}")
    print(f"  quality  : {quality}")
    print(f"  auth     : {auth}"
          + ("（プロキシがキーを注入する。セッション側にキーは不要）" if auth == "proxy" else ""))
    print()

    if provider == "mock":
        print(f"{WARN}mock なので確認するものが無い")
        return 0

    failures = 0

    problems = validate_size(size)
    if problems:
        print(f"{NG}size が不正")
        for p in problems:
            print(f"     - {p}")
        failures += 1
    else:
        print(f"{OK}size {size} は制約を満たしている")

    if auth == "proxy":
        print(f"{WARN}APIキー: auth=proxy のためセッション側では確認しない")
        headers: dict[str, str] = {}
    else:
        key = os.environ.get(key_env, "").strip()
        if key:
            print(f"{OK}APIキー {key_env} を読み込んだ（末尾4桁 ...{key[-4:]}）")
            headers = {"Authorization": f"Bearer {key}"}
        else:
            print(f"{NG}APIキー {key_env} が未設定。.env に書くこと")
            return failures + 1

    try:
        resp = requests.get(_models_endpoint(endpoint), headers=headers, timeout=30)
    except requests.exceptions.ProxyError:
        print(f"{NG}{host} に到達できない（エージェントプロキシが拒否）")
        print("     → クラウド環境のネットワーク設定でこのホストを許可するか、ローカルで実行すること")
        print("     → 詳しくは README の「ChatGPT Image と繋ぐ」を読むこと")
        logger.log(f"connect: {host} egress blocked", host=host, result="blocked")
        return failures + 1
    except requests.exceptions.RequestException as exc:
        print(f"{NG}{host} への接続に失敗: {exc}")
        logger.log(f"connect: {host} 接続失敗 {exc}", host=host, result="error")
        return failures + 1

    if resp.status_code >= 400:
        print(f"{NG}モデル一覧の取得に失敗")
        print("     " + explain_http_error(resp.status_code, resp.text).replace("\n", "\n     "))
        logger.log(f"connect: models {resp.status_code}", result="http_error")
        return failures + 1

    print(f"{OK}{host} に到達。認証も通った")
    ids = sorted(m.get("id", "") for m in (resp.json().get("data") or []))
    image_models = [m for m in ids if "image" in m]
    if image_models:
        print(f"{OK}このアカウントで使える画像モデル {len(image_models)} 件:")
        for m in image_models:
            print(f"       {m}{' ← config.yaml の設定' if m == model else ''}")
    else:
        print(f"{WARN}画像モデルが一覧に出てこない（一覧に載らない場合もある）")

    if model and model not in ids:
        print(f"{WARN}設定中の {model} は一覧に無い。使えるものに差し替えるか、")
        print("     --smoke で実際に叩けるか確かめること")

    logger.log("connect: 画像API 疎通OK", host=host, models=image_models, configured=model)

    if smoke:
        if failures:
            print(f"{WARN}先に上の NG を解消すること。--smoke は実行しない")
            return failures
        print("\n--- 実際に1枚編集する（課金が発生する）---")
        data = {"model": model, "size": size, "n": "1",
                "prompt": "この画像の色味はそのままに、中央に小さな白い円をひとつ描く。他は変更しない。"}
        if quality:
            data["quality"] = quality
        started = time.time()
        try:
            payload = post_images_edit(endpoint, headers, data, _smoke_image(project), timeout)
        except (ProxyBlockedError, Exception) as exc:
            print(f"{NG}編集リクエストが失敗")
            print("     " + str(exc).replace("\n", "\n     "))
            logger.log(f"connect smoke 失敗: {exc}", result="smoke_failed")
            return failures + 1
        out = project.log_dir / "connect" / "smoke_output.png"
        out.write_bytes(base64.b64decode(payload["data"][0]["b64_json"]))
        print(f"{OK}編集成功 {time.time() - started:.1f}秒 -> {out}")
        usage = payload.get("usage") or {}
        if usage:
            print(f"     usage: {usage}")
        logger.log(f"connect smoke OK -> {out}", result="smoke_ok", usage=usage)

    return failures


def check_video(project: Project, logger: RunLogger) -> int:
    """動画API（Gemini / MiniMax）を見る。返り値は未解決件数。"""
    section = dict(project.config.get("video") or {})
    provider = section.get("provider", "gemini")
    print()
    print("=" * 64)
    print(f" 動画API 連携チェック（provider: {provider}）")
    print("=" * 64)

    if provider == "mock":
        print(f"{WARN}mock なので確認するものが無い")
        return 0

    conf = dict(section.get(provider) or {})
    key_env = conf.get("api_key_env", "")
    model = conf.get("model", "")
    base_url = (conf.get("base_url") or "").rstrip("/")
    host = urlsplit(base_url).netloc
    print(f"  model    : {model}")
    print(f"  base_url : {base_url}")
    print()

    key = os.environ.get(key_env, "").strip() if key_env else ""
    if key:
        print(f"{OK}APIキー {key_env} を読み込んだ（末尾4桁 ...{key[-4:]}）")
    else:
        print(f"{NG}APIキー {key_env} が未設定。.env に書くこと")
        if provider == "gemini":
            print("     → Google AI Studio (aistudio.google.com) で発行したキーでよい")
        return 1

    if provider != "gemini":
        print(f"{WARN}{provider} はパス・項目名が未検証。公式ドキュメントで照合してから使うこと")
        print(f"{WARN}モデル一覧の確認には未対応。"
              "`python run.py --cut 01 --stage 2` で実地に試すこと")
        return 0

    try:
        resp = requests.get(f"{base_url}/models", params={"key": key, "pageSize": 200}, timeout=30)
    except requests.exceptions.ProxyError:
        print(f"{NG}{host} に到達できない（エージェントプロキシが拒否）")
        print("     → クラウド環境のネットワーク設定でこのホストを許可するか、ローカルで実行すること")
        return 1
    except requests.exceptions.RequestException as exc:
        print(f"{NG}{host} への接続に失敗: {exc}")
        return 1

    if resp.status_code >= 400:
        print(f"{NG}モデル一覧の取得に失敗 HTTP {resp.status_code}")
        print(f"     {resp.text[:400]}")
        if resp.status_code in (400, 403):
            print("     → キーが無効か、そのプロジェクトで Gemini API が有効になっていない")
        logger.log(f"connect: gemini models {resp.status_code}", result="http_error")
        return 1

    names = [m.get("name", "").split("/")[-1] for m in (resp.json().get("models") or [])]
    print(f"{OK}{host} に到達。認証も通った（モデル {len(names)} 件）")
    video_models = sorted(n for n in names if any(k in n for k in ("omni", "veo", "video")))
    if video_models:
        print(f"{OK}動画系モデル:")
        for n in video_models:
            print(f"       {n}{' ← config.yaml の設定' if n == model else ''}")
    else:
        print(f"{WARN}動画系モデルが一覧に出てこない")

    if model and model not in names:
        print(f"{WARN}設定中の {model} は一覧に無い")
        print("     → 動画生成は課金を有効にしたプロジェクトでないと使えないことが多い")
        print("     → 使えるモデルに差し替えるか、`python run.py --cut 01 --stage 2` で実地に試すこと")
    else:
        print(f"{OK}設定中の {model} は使える")

    logger.log("connect: 動画API 疎通OK", provider=provider, models=video_models)
    return 0


def run_connect(project: Project, logger: RunLogger, smoke: bool = False,
                video: bool = True) -> int:
    failures = check_image(project, logger, smoke=smoke)
    if video:
        failures += check_video(project, logger)

    print()
    if failures:
        print(f"未解決 {failures} 件。上の NG を潰すこと")
        return 1
    print("連携OK。`python run.py --stage 1` を回してよい"
          if smoke else "疎通OK。実際に1枚試すなら `python run.py connect --smoke`")
    return 0
