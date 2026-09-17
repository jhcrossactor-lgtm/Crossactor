"""OpenAI 画像編集API（gpt-image 系）アダプタ。

エンドポイント: POST https://api.openai.com/v1/images/edits  (multipart/form-data)
1枚目の image[] が編集対象、2枚目以降が参照画像。最大16枚。
モデル・サイズは config.yaml で差し替える（コード側にハードコードしない）。
"""

from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from ..util import RunLogger, require_api_key
from .base import ImageProvider, mime_of


class OpenAIImageProvider(ImageProvider):
    name = "openai"

    def __init__(
        self,
        model: str,
        size: str,
        endpoint: str = "https://api.openai.com/v1/images/edits",
        quality: str = "high",
        api_key_env: str = "OPENAI_API_KEY",
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
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.output_format = output_format

    def edit(self, prompt, images, dst, logger: RunLogger, cut_id: str) -> Path:
        key = require_api_key(self.api_key_env)
        dst.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "model": self.model,
            "prompt": prompt,
            "size": self.size,
            "n": "1",
        }
        if self.quality:
            data["quality"] = self.quality
        if self.output_format:
            data["output_format"] = self.output_format

        logger.log(
            f"cut{cut_id} 画像編集を依頼 model={self.model} size={self.size} "
            f"images={[p.name for p in images]}",
            cut=cut_id, stage="1", model=self.model, size=self.size,
            images=[str(p) for p in images],
        )

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            handles = []
            try:
                files = []
                for path in images:
                    fh = open(path, "rb")
                    handles.append(fh)
                    files.append(("image[]", (path.name, fh, mime_of(path))))
                resp = requests.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {key}"},
                    data=data,
                    files=files,
                    timeout=self.timeout_sec,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:800]}")
                payload = resp.json()
                b64 = payload["data"][0]["b64_json"]
                dst.write_bytes(base64.b64decode(b64))
                logger.log(f"cut{cut_id} 画像生成OK -> {dst}", cut=cut_id, stage="1", out=str(dst))
                return dst
            except Exception as exc:  # リトライして最後に投げる
                last_error = exc
                logger.log(f"cut{cut_id} 画像生成 失敗 (試行{attempt}/{self.max_retries}): {exc}",
                           cut=cut_id, stage="1", error=str(exc))
                if attempt < self.max_retries:
                    time.sleep(5 * attempt)
            finally:
                for fh in handles:
                    fh.close()
        raise RuntimeError(f"cut{cut_id} 画像生成に失敗: {last_error}")
