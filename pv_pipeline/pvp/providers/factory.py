"""config.yaml から適切なプロバイダを組み立てる。"""

from __future__ import annotations

from typing import Any

from .base import ImageProvider, VideoProvider


def build_image_provider(config: dict[str, Any], override: str | None = None) -> ImageProvider:
    section = dict(config.get("image") or {})
    provider = override or section.get("provider", "openai")
    section.pop("provider", None)
    if provider == "openai":
        from .openai_image import OpenAIImageProvider

        return OpenAIImageProvider(**section)
    if provider == "mock":
        from .mock import MockImageProvider

        return MockImageProvider(size=section.get("size", "2048x1152"))
    raise SystemExit(f"未知の image provider: {provider}")


def build_video_provider(config: dict[str, Any], override: str | None = None) -> VideoProvider:
    section = dict(config.get("video") or {})
    provider = override or section.get("provider", "gemini")
    common = {k: v for k, v in section.items() if k not in {"provider", "gemini", "minimax"}}
    if provider == "gemini":
        from .gemini_video import GeminiVideoProvider

        return GeminiVideoProvider(**{**common, **(section.get("gemini") or {})})
    if provider == "minimax":
        from .minimax_video import MiniMaxVideoProvider

        return MiniMaxVideoProvider(**{**common, **(section.get("minimax") or {})})
    if provider == "mock":
        from .mock import MockVideoProvider

        assemble = config.get("assemble") or {}
        return MockVideoProvider(
            width=assemble.get("width", 1920),
            height=assemble.get("height", 1080),
            fps=assemble.get("fps", 24),
        )
    raise SystemExit(f"未知の video provider: {provider}")
