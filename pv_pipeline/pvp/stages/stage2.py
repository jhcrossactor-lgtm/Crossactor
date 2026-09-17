"""工程4/5: image-to-video と、MOV素材の 16:9 切り出し。"""

from __future__ import annotations

from pathlib import Path

from .. import media
from ..cuts import cut_by_id, load_cuts
from ..providers.factory import build_video_provider
from ..util import Project, RunLogger


def run_stage2(
    project: Project,
    logger: RunLogger,
    only_cut: str | None = None,
    provider_override: str | None = None,
) -> list[Path]:
    config = project.config
    assemble_cfg = config.get("assemble") or {}
    width = int(assemble_cfg.get("width", 1920))
    height = int(assemble_cfg.get("height", 1080))
    fps = int(assemble_cfg.get("fps", 24))
    keep_audio = bool((config.get("music") or {}).get("keep_clip_audio", False))

    cuts = load_cuts(project)
    if only_cut:
        cuts = [cut_by_id(project, only_cut)]

    provider = None
    produced: list[Path] = []
    for cut in cuts:
        if cut.video_mode == "passthrough":
            src = cut.source_path()
            logger.log(f"cut{cut.id} 実写素材を中央16:9で切り出し ({src.name})",
                       cut=cut.id, stage="2", mode="passthrough")
            media.video_center_16x9(src, cut.stage2_path(), cut.duration,
                                    width, height, fps, logger)
            produced.append(cut.stage2_path())
            continue

        source_image = cut.stage1_path()
        if not source_image.exists():
            # 画像編集をスキップしたカットは元素材をそのまま動画化する
            source_image = cut.source_path()
            logger.log(f"cut{cut.id} stage1画像が無いので元素材を使う ({source_image.name})",
                       cut=cut.id, stage="2")

        if provider is None:
            provider = build_video_provider(config, provider_override)

        prompt = cut.video_prompt(config)
        prompt_file = logger.save_prompt(
            cut.id, "stage2", prompt,
            {"cut": cut.id, "provider": provider.name,
             "image": source_image.name, "duration": cut.duration},
        )
        logger.log(f"cut{cut.id} プロンプト保存: {prompt_file.name}", cut=cut.id, stage="2")

        raw = cut.stage2_raw_path()
        provider.image_to_video(prompt, source_image, raw, cut.duration, logger, cut.id)
        media.normalize_clip(raw, cut.stage2_path(), cut.duration, width, height, fps,
                             keep_audio=keep_audio and provider.generates_audio, logger=logger)
        logger.log(f"cut{cut.id} 尺そろえ完了 {cut.duration}s -> {cut.stage2_path()}",
                   cut=cut.id, stage="2")
        produced.append(cut.stage2_path())

    return produced
