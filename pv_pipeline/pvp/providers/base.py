"""プロバイダの共通インタフェースと小物。"""

from __future__ import annotations

import base64
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..util import RunLogger


def b64_of(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def mime_of(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "image/png"


def dig(obj: Any, *keys: str) -> Any:
    """ネストした dict を安全に辿る。"""
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def find_first(obj: Any, key: str) -> Any:
    """レスポンス構造が変わっても拾えるよう、キーを再帰探索する。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_first(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_first(item, key)
            if found is not None:
                return found
    return None


class ImageProvider(ABC):
    name = "image"

    @abstractmethod
    def edit(
        self,
        prompt: str,
        images: list[Path],
        dst: Path,
        logger: RunLogger,
        cut_id: str,
    ) -> Path:
        """images[0] を編集対象、以降を参照として渡し、dst に書き出す。"""


class VideoProvider(ABC):
    name = "video"
    generates_audio = False

    @abstractmethod
    def image_to_video(
        self,
        prompt: str,
        image: Path,
        dst: Path,
        duration: float,
        logger: RunLogger,
        cut_id: str,
    ) -> Path:
        """1枚の静止画から動画を作り、dst に書き出す。"""
