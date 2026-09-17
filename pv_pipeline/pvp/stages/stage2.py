"""工程4/5: image-to-video と、MOV素材の 16:9 切り出し。"""

from __future__ import annotations

from pathlib import Path

from .. import media
from ..cuts import cut_by_id, load_cuts
from ..providers.factory import build_video_provider
from ..util import Project, RunLogger


def _start_crop(image: Path, cut, logger: RunLogger) -> Path:
    """最初のコマを寄せた構図にするため、静止画を 16:9 のまま切り出して元の解像度に戻す。"""
    from PIL import Image

    spec = cut.video_start_crop
    cx, cy = (list(spec.get("center") or [0.5, 0.5]) + [0.5, 0.5])[:2]
    size = float(spec.get("size", 0.7))
    with Image.open(image) as im:
        w, h = im.size
        cw, ch = round(w * size), round(h * size)
        left = min(max(round(cx * w - cw / 2), 0), w - cw)
        top = min(max(round(cy * h - ch / 2), 0), h - ch)
        out = image.parent / "_start_crop" / f"cut{cut.id}_start.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").crop((left, top, left + cw, top + ch)).resize((w, h), Image.LANCZOS).save(out)
    logger.log(f"cut{cut.id} 最初のコマを寄せて切り出し size={size} center=({cx},{cy}) -> {out.name}",
               cut=cut.id, stage="2", start_crop=spec)
    return out


def run_stage2(
    project: Project,
    logger: RunLogger,
    only_cut: str | None = None,
    provider_override: str | None = None,
    reuse_raw: bool = False,
) -> list[Path]:
    config = project.config
    assemble_cfg = config.get("assemble") or {}
    width = int(assemble_cfg.get("width", 1920))
    height = int(assemble_cfg.get("height", 1080))
    fps = int(assemble_cfg.get("fps", 24))
    keep_audio = bool((config.get("music") or {}).get("keep_clip_audio", False))

    cuts = load_cuts(project)
    if only_cut:
        cuts = [cut_by_id(project, t.strip()) for t in str(only_cut).split(",") if t.strip()]

    provider = None
    produced: list[Path] = []
    for cut in cuts:
        if cut.video_mode == "passthrough":
            src = cut.source_path()
            logger.log(f"cut{cut.id} 実写素材を中央16:9で切り出し ({src.name})",
                       cut=cut.id, stage="2", mode="passthrough")
            v = cut.raw.get("video") or {}
            media.video_center_16x9(src, cut.stage2_path(), cut.duration,
                                    width, height, fps, logger,
                                    start=float(v.get("start", 0.0)),
                                    crop_x=float(v.get("crop_x", 0.5)),
                                    crop_y=float(v.get("crop_y", 0.5)))
            produced.append(cut.stage2_path())
            continue

        source_image = cut.stage1_path()
        if not source_image.exists():
            # 画像編集をスキップしたカットは元素材をそのまま動画化する
            source_image = cut.source_path()
            logger.log(f"cut{cut.id} stage1画像が無いので元素材を使う ({source_image.name})",
                       cut=cut.id, stage="2")

        if cut.video_start_crop:
            source_image = _start_crop(source_image, cut, logger)

        raw = cut.stage2_raw_path()
        generates_audio = False
        if reuse_raw and raw.exists():
            # API を呼ばず、生成済みの原本から仕上げ（尺そろえ・ズーム）だけやり直す
            logger.log(f"cut{cut.id} 生成済みの原本を再利用（APIは呼ばない）: {raw.name}",
                       cut=cut.id, stage="2", reuse_raw=True)
        else:
            if reuse_raw:
                logger.log(f"cut{cut.id} 原本が無いので生成する", cut=cut.id, stage="2")
            if provider is None:
                provider = build_video_provider(config, provider_override)

            prompt = cut.video_prompt(config)
            prompt_file = logger.save_prompt(
                cut.id, "stage2", prompt,
                {"cut": cut.id, "provider": provider.name,
                 "image": source_image.name, "duration": cut.duration},
            )
            logger.log(f"cut{cut.id} プロンプト保存: {prompt_file.name}", cut=cut.id, stage="2")
            provider.image_to_video(prompt, source_image, raw, cut.duration, logger, cut.id)
            generates_audio = provider.generates_audio

        media.normalize_clip(raw, cut.stage2_path(), cut.duration, width, height, fps,
                             keep_audio=keep_audio and generates_audio,
                             zoom=cut.video_zoom, logger=logger)
        if cut.video_overlays:
            from ..overlay import apply_overlays

            plain = cut.stage2_path().with_name(f"{cut.stage2_path().stem}_notext.mp4")
            cut.stage2_path().replace(plain)
            apply_overlays(plain, cut.stage2_path(), cut.video_overlays,
                           width, height, fps, cut.duration, logger)
        logger.log(f"cut{cut.id} 尺そろえ完了 {cut.duration}s -> {cut.stage2_path()}",
                   cut=cut.id, stage="2")
        produced.append(cut.stage2_path())

    return produced
