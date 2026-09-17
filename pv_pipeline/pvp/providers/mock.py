"""APIを叩かずに配線だけ確認するためのモック。--provider mock で使う。"""

from __future__ import annotations

from pathlib import Path

from .. import media
from ..util import RunLogger
from .base import ImageProvider, VideoProvider


class MockImageProvider(ImageProvider):
    name = "mock"

    def __init__(self, size: str = "2048x1152", **_: object) -> None:
        self.width, _, self.height = size.partition("x")

    def edit(self, prompt, images, dst, logger: RunLogger, cut_id: str) -> Path:
        """編集対象を 16:9 にリサイズしてコピーするだけ。"""
        from ..util import ffmpeg_bin, run_cmd

        dst.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
        )
        run_cmd([ffmpeg_bin(), "-y", "-i", str(images[0]), "-vf", vf, str(dst)], logger)
        logger.log(f"[mock] cut{cut_id} 画像生成をスキップして素材を16:9化した", cut=cut_id)
        return dst


class MockVideoProvider(VideoProvider):
    name = "mock"

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 24, **_: object) -> None:
        self.width, self.height, self.fps = width, height, fps

    def image_to_video(self, prompt, image, dst, duration, logger: RunLogger, cut_id: str) -> Path:
        media.still_to_clip(image, dst, duration, self.width, self.height, self.fps, logger)
        logger.log(f"[mock] cut{cut_id} 動画生成をスキップして静止画を{duration}秒化した", cut=cut_id)
        return dst
