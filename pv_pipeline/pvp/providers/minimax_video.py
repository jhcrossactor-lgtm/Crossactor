"""MiniMax H3 image-to-video アダプタ（Video Generation V2）。

公式ドキュメント（platform.minimax.io の video-generation / video-generation-v2-create）で確認済み:
  POST {base}/v2/video_generation                    -> task_id
  GET  {base}/v2/query/video_generation/{task_id}    -> task.status / 成功時は動画URL
画像は content 配列に image_url（data URI の base64 可）・role=first_frame で渡す。
尺は 4〜15 秒の整数（H3）。縦横比は入力画像から決まる（adaptive）。
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from ..util import RunLogger, require_api_key
from .base import VideoProvider, b64_of, find_first, mime_of


class MiniMaxVideoProvider(VideoProvider):
    name = "minimax"

    def __init__(
        self,
        model: str = "MiniMax-H3",
        base_url: str = "https://api.minimax.io",
        api_key_env: str = "MINIMAX_API_KEY",
        resolution: str = "2K",
        min_duration_sec: int = 4,
        max_duration_sec: int = 15,
        prompt_expansion_mode: str = "disabled",
        poll_interval_sec: int = 10,
        poll_timeout_sec: int = 1200,
        timeout_sec: int = 120,
        **_: object,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.resolution = resolution
        self.min_duration_sec = min_duration_sec
        self.max_duration_sec = max_duration_sec
        self.prompt_expansion_mode = prompt_expansion_mode
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec
        self.timeout_sec = timeout_sec

    def image_to_video(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        key = require_api_key(self.api_key_env)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        dst.parent.mkdir(parents=True, exist_ok=True)

        # 下限より短いカットは下限で作り、stage2 で目標秒数に切りそろえる
        request_duration = min(max(int(round(duration)), self.min_duration_sec), self.max_duration_sec)
        body: dict = {
            "model": self.model,
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_of(image)};base64,{b64_of(image)}"},
                    "role": "first_frame",
                },
            ],
            "duration": request_duration,
            "resolution": self.resolution,
        }
        if self.prompt_expansion_mode:
            # disabled にしておかないと、プロンプトが勝手に書き換えられて指示がぶれる
            body["extra"] = {"prompt_expansion_mode": self.prompt_expansion_mode}

        logger.log(
            f"cut{cut_id} 動画生成を依頼 (minimax v2) model={self.model} "
            f"resolution={self.resolution} duration={request_duration}s(目標{duration}s)",
            cut=cut_id, stage="2", model=self.model, resolution=self.resolution,
            duration=request_duration, image=str(image),
        )
        started = time.time()
        resp = requests.post(f"{self.base_url}/v2/video_generation", headers=headers,
                             json=body, timeout=self.timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"video_generation HTTP {resp.status_code}: {resp.text[:800]}")
        created = resp.json()
        base = created.get("base_resp") or {}
        if base.get("status_code") not in (None, 0):
            raise RuntimeError(f"cut{cut_id} 作成失敗: {base}")
        task_id = find_first(created, "task_id")
        if not task_id:
            raise RuntimeError(f"task_id が返ってこない: {str(created)[:500]}")
        logger.log(f"cut{cut_id} タスク作成 task_id={task_id}", cut=cut_id, stage="2", task_id=task_id)

        deadline = time.time() + self.poll_timeout_sec
        while True:
            if time.time() > deadline:
                raise RuntimeError(f"cut{cut_id} 動画生成がタイムアウト ({self.poll_timeout_sec}s)")
            time.sleep(self.poll_interval_sec)
            poll = requests.get(f"{self.base_url}/v2/query/video_generation/{task_id}",
                                headers=headers, timeout=self.timeout_sec)
            if poll.status_code >= 400:
                raise RuntimeError(f"query HTTP {poll.status_code}: {poll.text[:500]}")
            state = poll.json()
            status = str(find_first(state, "status") or "").lower()
            logger.log(f"cut{cut_id} 生成待ち... status={status}", cut=cut_id, stage="2")
            if status == "succeeded":
                break
            if status in {"failed", "cancelled"}:
                raise RuntimeError(f"cut{cut_id} 動画生成 {status}: {str(state)[:800]}")

        url = find_first(state, "url") or find_first(state, "download_url")
        if not url:
            raise RuntimeError(f"cut{cut_id} 動画URLが見つからない: {str(state)[:800]}")
        got = requests.get(url, timeout=self.timeout_sec * 5)
        if got.status_code >= 400:
            raise RuntimeError(f"動画DL HTTP {got.status_code}")
        dst.write_bytes(got.content)
        logger.log(f"cut{cut_id} 動画生成OK {time.time() - started:.0f}秒 -> {dst}",
                   cut=cut_id, stage="2", out=str(dst))
        return dst
