"""MiniMax H3 (Hailuo) image-to-video アダプタ。

非同期3ステップ: 生成タスク作成 -> task_id でステータス照会 -> file_id からDL URL取得。
注意: MiniMax 公式ドキュメント (platform.minimax.io) は本実装時のネットワークから
到達できず、パス・フィールド名は**未検証**。config.yaml 側で全部差し替えられる。
初回実行前に公式ドキュメントで照合すること。
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
        model: str,
        base_url: str = "https://api.minimax.io/v1",
        create_path: str = "/video_generation",
        status_path: str = "/query/video_generation",
        retrieve_path: str = "/files/retrieve",
        api_key_env: str = "MINIMAX_API_KEY",
        group_id_env: str = "MINIMAX_GROUP_ID",
        resolution: str = "1080P",
        min_duration_sec: int = 5,
        image_field: str = "first_frame_image",
        duration_field: str = "duration",
        prompt_field: str = "prompt",
        image_as_data_uri: bool = True,
        generate_audio: bool = False,
        extra_payload: dict | None = None,
        poll_interval_sec: int = 10,
        poll_timeout_sec: int = 1200,
        timeout_sec: int = 120,
        **_: object,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.create_path = create_path
        self.status_path = status_path
        self.retrieve_path = retrieve_path
        self.api_key_env = api_key_env
        self.group_id_env = group_id_env
        self.resolution = resolution
        self.min_duration_sec = min_duration_sec
        self.image_field = image_field
        self.duration_field = duration_field
        self.prompt_field = prompt_field
        self.image_as_data_uri = image_as_data_uri
        self.generates_audio = bool(generate_audio)
        self.extra_payload = extra_payload or {}
        self.poll_interval_sec = poll_interval_sec
        self.poll_timeout_sec = poll_timeout_sec
        self.timeout_sec = timeout_sec

    def image_to_video(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        key = require_api_key(self.api_key_env)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        dst.parent.mkdir(parents=True, exist_ok=True)

        # H3 は最短尺の下限があるため、下限で作って stage2 側で目標秒数に詰める。
        request_duration = max(int(round(duration)), self.min_duration_sec)
        encoded = b64_of(image)
        payload = {
            "model": self.model,
            self.prompt_field: prompt,
            self.image_field: (
                f"data:{mime_of(image)};base64,{encoded}" if self.image_as_data_uri else encoded
            ),
            self.duration_field: request_duration,
            "resolution": self.resolution,
        }
        payload.update(self.extra_payload)

        logger.log(
            f"cut{cut_id} 動画生成を依頼 (minimax) model={self.model} "
            f"duration={request_duration}s(目標{duration}s)",
            cut=cut_id, stage="2", model=self.model,
            payload={k: v for k, v in payload.items() if k != self.image_field},
        )
        resp = requests.post(self.base_url + self.create_path, headers=headers,
                             json=payload, timeout=self.timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"create HTTP {resp.status_code}: {resp.text[:800]}")
        created = resp.json()
        task_id = find_first(created, "task_id") or find_first(created, "taskId")
        if not task_id:
            raise RuntimeError(f"task_id が返ってこない: {str(created)[:500]}")

        deadline = time.time() + self.poll_timeout_sec
        file_id = None
        while True:
            if time.time() > deadline:
                raise RuntimeError(f"cut{cut_id} 動画生成がタイムアウト ({self.poll_timeout_sec}s)")
            time.sleep(self.poll_interval_sec)
            poll = requests.get(self.base_url + self.status_path, headers=headers,
                                params={"task_id": task_id}, timeout=self.timeout_sec)
            if poll.status_code >= 400:
                raise RuntimeError(f"query HTTP {poll.status_code}: {poll.text[:500]}")
            state = poll.json()
            status = str(find_first(state, "status") or "").lower()
            logger.log(f"cut{cut_id} 生成待ち... status={status}", cut=cut_id, stage="2")
            if status in {"success", "succeeded", "finished"}:
                file_id = find_first(state, "file_id") or find_first(state, "fileId")
                break
            if status in {"fail", "failed", "error"}:
                raise RuntimeError(f"cut{cut_id} 動画生成失敗: {str(state)[:500]}")

        if not file_id:
            raise RuntimeError(f"cut{cut_id} file_id が取れない")

        params = {"file_id": file_id}
        import os

        group_id = os.environ.get(self.group_id_env, "").strip()
        if group_id:
            params["GroupId"] = group_id
        meta = requests.get(self.base_url + self.retrieve_path, headers=headers,
                            params=params, timeout=self.timeout_sec)
        if meta.status_code >= 400:
            raise RuntimeError(f"retrieve HTTP {meta.status_code}: {meta.text[:500]}")
        download_url = find_first(meta.json(), "download_url") or find_first(meta.json(), "url")
        if not download_url:
            raise RuntimeError(f"download_url が取れない: {meta.text[:500]}")

        got = requests.get(download_url, timeout=self.timeout_sec * 5)
        if got.status_code >= 400:
            raise RuntimeError(f"動画DL HTTP {got.status_code}")
        dst.write_bytes(got.content)
        logger.log(f"cut{cut_id} 動画生成OK -> {dst}", cut=cut_id, stage="2", out=str(dst))
        return dst
