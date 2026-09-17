"""工程6/7: xfade結合・フェードアウト・音楽の載せ込み。"""

from __future__ import annotations

from pathlib import Path

from .. import media
from ..cuts import load_cuts
from ..util import Project, RunLogger


def _resolve_path(project: Project, name: str) -> Path:
    """相対パスは input/ 基準、次にプロジェクト直下、最後にカレント基準で探す。"""
    path = Path(name)
    if path.is_absolute():
        return path
    for base in (project.input_dir, project.root, Path.cwd()):
        candidate = base / path
        if candidate.exists():
            return candidate
    return project.input_dir / path


def resolve_music(project: Project, logger: RunLogger) -> Path | None:
    """音楽トラックを決める。用意できなければ None（=無音）を返す。

    画像/動画APIのどちらにも 30秒級のBGMを生成する公開エンドポイントが無いため、
    既定は「ファイルがあれば使う、無ければ無音」。
    """
    music_cfg = project.config.get("music") or {}
    if not music_cfg.get("enabled", True):
        logger.log("音楽: 設定で無効化されているため無音で出力する", stage="3", music="disabled")
        return None

    name = (music_cfg.get("file") or "").strip()
    if name:
        path = _resolve_path(project, name)
        if path.exists():
            logger.log(f"音楽: {path} を使用", stage="3", music=str(path))
            return path
        logger.log(f"音楽: 指定ファイル {path} が無い。無音で出力する", stage="3", music="missing")
        return None

    logger.log(
        "音楽: 生成元が無いため無音で出力する。"
        "（BGMを入れるときは config.yaml の music.file に音源を指定して stage3 だけ再実行）",
        stage="3", music="none",
    )
    return None


def run_stage3(project: Project, logger: RunLogger, music_override: Path | None = None) -> Path:
    config = project.config
    assemble_cfg = config.get("assemble") or {}
    width = int(assemble_cfg.get("width", 1920))
    height = int(assemble_cfg.get("height", 1080))
    fps = int(assemble_cfg.get("fps", 24))
    xfade = float(assemble_cfg.get("xfade_duration", 0.5))
    fade_out = float(assemble_cfg.get("fade_out_duration", 2.0))
    out_name = assemble_cfg.get("output", "pv_16x9.mp4")

    clips: list[Path] = []
    missing: list[str] = []
    for cut in load_cuts(project):
        path = cut.stage2_path()
        if path.exists():
            clips.append(path)
        else:
            missing.append(cut.id)
    if missing:
        raise SystemExit(
            f"stage2 の出力が足りない: cut{', cut'.join(missing)} — 先に stage2 を回すこと"
        )

    if music_override is not None:
        music = _resolve_path(project, str(music_override))
        if not music.exists():
            raise SystemExit(f"--music で指定した音源が見つからない: {music_override}")
        logger.log(f"音楽: {music} を使用 (--music指定)", stage="3", music=str(music))
    else:
        music = resolve_music(project, logger)
    dst = project.output_dir / out_name
    logger.log(
        f"結合開始 clips={len(clips)} xfade={xfade}s fadeout={fade_out}s",
        stage="3", clips=[str(c) for c in clips],
    )
    out, total = media.assemble(
        clips, dst, xfade, fade_out, width, height, fps,
        music=music,
        keep_clip_audio=bool((config.get("music") or {}).get("keep_clip_audio", False)),
        logger=logger,
    )
    logger.log(
        f"完成: {out} 尺={total:.2f}秒 音声={'あり' if music else 'なし(無音)'}",
        stage="3", output=str(out), duration=round(total, 2), has_music=bool(music),
    )
    return out
