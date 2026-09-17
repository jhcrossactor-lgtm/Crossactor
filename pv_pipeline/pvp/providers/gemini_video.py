"""Gemini image-to-video アダプタ（Gemini API / generativelanguage）。

モデルによって呼び方が違う（ListModels の supportedGenerationMethods で確認済み）:
  Gemini Omni (gemini-omni-*) : Interactions API  POST {base}/interactions
  Veo (veo-*)                 : POST {base}/models/{model}:predictLongRunning -> Operation をポーリング
config.yaml の video.gemini.api で明示もできる（interactions / predict）。
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from ..util import RunLogger, require_api_key
from .base import VideoProvider, b64_of, find_first, mime_of


class GeminiVideoProvider(VideoProvider):
    name = "gemini"

    def __init__(
        self,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        api_key_env: str = "GEMINI_API_KEY",
        aspect_ratio: str = "16:9",
        resolution: str = "1080p",
        generate_audio: bool = False,
        negative_prompt: str = "",
        duration_param: str = "durationSeconds",
        duration_as_string: bool = False,
        extra_parameters: dict | None = None,
        poll_interval_sec: int = 10,
        poll_timeout_sec: int = 900,
        timeout_sec: int = 120,
        api: str = "",
        delivery: str = "uri",
        **_: object,
    ) -> None:
        # api 未指定なら、Omni 系は Interactions API、それ以外（Veo）は predictLongRunning
        self.api = api or ("interactions" if "omni" in model else "predict")
        self.delivery = delivery
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.aspect_ratio = aspect_ratio
        self.resolution = resolution
        self.generate_audio = generate_audio
        self.generates_audio = bool(generate_audio)
        self.negative_prompt = negative_prompt
        self.duration_param = duration_param
        self.duration_as_string = duration_as_string
        self.extra_parameters = extra_parameters or {}
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec
        self.timeout_sec = timeout_sec

    def _parameters(self, duration: float) -> dict:
        seconds = int(round(duration))
        params: dict = {
            "aspectRatio": self.aspect_ratio,
            self.duration_param: f"{seconds}s" if self.duration_as_string else seconds,
        }
        if self.resolution:
            params["resolution"] = self.resolution
        if self.negative_prompt:
            params["negativePrompt"] = self.negative_prompt
        params["generateAudio"] = bool(self.generate_audio)
        params.update(self.extra_parameters)
        return params

    def image_to_video(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        if self.api == "interactions":
            return self._interactions(prompt, image, dst, duration, logger, cut_id)
        return self._predict_long_running(prompt, image, dst, duration, logger, cut_id)

    # ------------------------------------------------------------------ #
    # Gemini Omni: Interactions API
    #   POST {base}/interactions            -> steps[].model_output.content[].video
    #   delivery=uri のとき GET {base}/files/{id} で ACTIVE を待ち、
    #   GET {base}/files/{id}:download?alt=media で取得する。
    # 尺・ネガティブプロンプトは指定できない（尺は stage2 で目標秒数に切りそろえる）。
    # ------------------------------------------------------------------ #
    def _interactions(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        import base64
        import json

        key = require_api_key(self.api_key_env)
        dst.parent.mkdir(parents=True, exist_ok=True)

        text = prompt
        text += f"\n\n映像の長さは約{int(round(duration))}秒。"
        if self.negative_prompt:
            text += f"\n禁止：{self.negative_prompt}"

        response_format: dict = {"type": "video", "aspect_ratio": self.aspect_ratio}
        if self.resolution:
            response_format["resolution"] = self.resolution
        if self.delivery:
            response_format["delivery"] = self.delivery
        body = {
            "model": self.model,
            "input": [
                {"type": "image", "data": b64_of(image), "mime_type": mime_of(image)},
                {"type": "text", "text": text},
            ],
            "response_format": response_format,
        }
        logger.log(
            f"cut{cut_id} 動画生成を依頼 (gemini interactions) model={self.model} "
            f"resolution={self.resolution} 目標{duration}s",
            cut=cut_id, stage="2", model=self.model, response_format=response_format, image=str(image),
        )
        started = time.time()
        resp = requests.post(f"{self.base_url}/interactions", params={"key": key},
                             json=body, timeout=self.poll_timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"interactions HTTP {resp.status_code}: {resp.text[:800]}")
        payload = resp.json()

        # 調査用に、動画本体を除いたレスポンスをログに残す
        def _strip(obj):
            if isinstance(obj, dict):
                return {k: ("<base64 省略>" if k == "data" and isinstance(v, str) and len(v) > 200 else _strip(v))
                        for k, v in obj.items()}
            if isinstance(obj, list):
                return [_strip(x) for x in obj]
            return obj
        debug = dst.parent / f"{dst.stem}_response.json"
        debug.write_text(json.dumps(_strip(payload), ensure_ascii=False, indent=2), encoding="utf-8")

        video = None
        for step in payload.get("steps") or []:
            if step.get("type") != "model_output":
                continue
            for item in step.get("content") or []:
                if item.get("type") == "video":
                    video = item
        if video is None:
            raise RuntimeError(
                f"cut{cut_id} 動画が返ってこない status={payload.get('status')} "
                f"（レスポンスは {debug.name} に保存）"
            )

        if video.get("data"):
            dst.write_bytes(base64.b64decode(video["data"]))
        else:
            uri = video.get("uri") or video.get("file_uri") or find_first(video, "uri")
            if not uri:
                raise RuntimeError(f"cut{cut_id} 動画の data も uri も無い（{debug.name}）")
            file_id = uri.rstrip("/").split("/files/")[-1].split(":")[0].split("?")[0]
            deadline = time.time() + self.poll_timeout_sec
            while True:
                meta = requests.get(f"{self.base_url}/files/{file_id}", params={"key": key},
                                    timeout=self.timeout_sec)
                if meta.status_code >= 400:
                    raise RuntimeError(f"files.get HTTP {meta.status_code}: {meta.text[:500]}")
                state = str((meta.json().get("state") or "")).upper()
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError(f"cut{cut_id} 動画ファイルの処理に失敗: {meta.text[:500]}")
                if time.time() > deadline:
                    raise RuntimeError(f"cut{cut_id} 動画ファイルの準備がタイムアウト")
                logger.log(f"cut{cut_id} ファイル準備待ち... state={state}", cut=cut_id, stage="2")
                time.sleep(self.poll_interval_sec)
            got = requests.get(f"{self.base_url}/files/{file_id}:download",
                               params={"alt": "media", "key": key}, timeout=self.timeout_sec * 5)
            if got.status_code >= 400:
                raise RuntimeError(f"動画DL HTTP {got.status_code}: {got.text[:300]}")
            dst.write_bytes(got.content)

        usage = payload.get("usage") or payload.get("usage_metadata") or {}
        logger.log(
            f"cut{cut_id} 動画生成OK {time.time() - started:.0f}秒 -> {dst}",
            cut=cut_id, stage="2", out=str(dst), usage=usage,
        )
        return dst

    # ------------------------------------------------------------------ #
    # Veo: predictLongRunning
    # ------------------------------------------------------------------ #
    def _predict_long_running(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        key = require_api_key(self.api_key_env)
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.base_url}/models/{self.model}:predictLongRunning"
        body = {
            "instances": [{
                "prompt": prompt,
                "image": {"bytesBase64Encoded": b64_of(image), "mimeType": mime_of(image)},
            }],
            "parameters": self._parameters(duration),
        }
        logger.log(
            f"cut{cut_id} 動画生成を依頼 (gemini) model={self.model} duration={duration}s",
            cut=cut_id, stage="2", model=self.model,
            parameters=body["parameters"], image=str(image),
        )
        resp = requests.post(url, params={"key": key}, json=body, timeout=self.timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"predictLongRunning HTTP {resp.status_code}: {resp.text[:800]}")
        operation = resp.json()
        op_name = operation.get("name")
        if not op_name:
            raise RuntimeError(f"operation name が返ってこない: {str(operation)[:500]}")

        deadline = time.time() + self.poll_timeout_sec
        while not operation.get("done"):
            if time.time() > deadline:
                raise RuntimeError(f"cut{cut_id} 動画生成がタイムアウト ({self.poll_timeout_sec}s)")
            time.sleep(self.poll_interval_sec)
            poll = requests.get(f"{self.base_url}/{op_name}", params={"key": key},
                                timeout=self.timeout_sec)
            if poll.status_code >= 400:
                raise RuntimeError(f"operations.get HTTP {poll.status_code}: {poll.text[:500]}")
            operation = poll.json()
            logger.log(f"cut{cut_id} 生成待ち... done={operation.get('done')}", cut=cut_id, stage="2")

        if operation.get("error"):
            raise RuntimeError(f"cut{cut_id} 動画生成エラー: {operation['error']}")

        response = operation.get("response", {})
        uri = find_first(response, "uri")
        if uri:
            got = requests.get(uri, params={"key": key}, timeout=self.timeout_sec * 5)
            if got.status_code >= 400:
                raise RuntimeError(f"動画DL HTTP {got.status_code}: {got.text[:300]}")
            dst.write_bytes(got.content)
        else:
            raw = find_first(response, "bytesBase64Encoded") or find_first(response, "videoBytes")
            if not raw:
                raise RuntimeError(f"動画データが見つからない: {str(response)[:800]}")
            import base64 as _b64

            dst.write_bytes(_b64.b64decode(raw))
        logger.log(f"cut{cut_id} 動画生成OK -> {dst}", cut=cut_id, stage="2", out=str(dst))
        return dst
