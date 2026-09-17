"""Gemini image-to-video アダプタ（Gemini API / generativelanguage）。

エンドポイント（公式ディスカバリで確認済み）:
  POST {base}/models/{model}:predictLongRunning?key=KEY   -> Operation
  GET  {base}/{operation.name}?key=KEY                     -> Operation (done を待つ)
instances / parameters は API 上 free-form (type: any) なので、
パラメータ名は config.yaml 側で差し替えられるようにしてある。
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
        **_: object,
    ) -> None:
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
