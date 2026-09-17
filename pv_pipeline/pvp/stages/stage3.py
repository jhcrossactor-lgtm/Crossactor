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


def transition_kwargs(project: Project) -> dict:
    """つなぎの設定を集める。cuts.yaml の transition_in（そのカットに入るときの切り替え）と、
    config の assemble.default_transition / fade_in_duration。"""
    cfg = project.config.get("assemble") or {}
    cuts = load_cuts(project)
    transitions = [(c.raw.get("transition_in") or {}) for c in cuts[1:]]
    return {
        "transitions": transitions,
        "default_transition": cfg.get("default_transition", "fade"),
        "fade_in_duration": float(cfg.get("fade_in_duration", 0.0)),
    }


def _assemble_with_end_card(clips, dst, xfade, fade_out, width, height, fps,
                            end_card: dict, music, project: Project, logger: RunLogger):
    """本編を黒へフェードアウトさせたあと、黒地に施設名を出すエンドカードをつなぐ。"""
    from ..overlay import black_card
    from ..util import ffmpeg_bin, run_cmd

    work = project.output_dir / "_work"
    work.mkdir(parents=True, exist_ok=True)
    main, main_total = media.assemble(clips, work / "main.mp4", xfade, fade_out,
                                      width, height, fps, music=None, logger=logger,
                                      **transition_kwargs(project))
    card_dur = float(end_card.get("duration", 4.0))
    if end_card.get("style") == "bull_shine":
        from ..endcard import render_bull_shine_card

        card = render_bull_shine_card(work / "end_card.mp4", end_card,
                                      _resolve_path(project, end_card["background"]),
                                      width, height, fps, logger)
    else:
        card = black_card(work / "end_card.mp4", list(end_card.get("overlays") or []),
                          width, height, fps, card_dur, logger)
    total = main_total + card_dur

    cmd = [ffmpeg_bin(), "-y", "-i", str(main), "-i", str(card)]
    filt = "[0:v][1:v]concat=n=2:v=1:a=0[v]"
    maps = ["-map", "[v]"]
    if music is not None:
        cmd += ["-i", str(music)]
        filt += (f";[2:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},afade=t=in:st=0:d=1.0,"
                 f"afade=t=out:st={max(total - 2.5, 0):.3f}:d=2.5[a]")
        maps += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    else:
        maps += ["-an"]
    run_cmd(cmd + ["-filter_complex", filt] + maps +
            ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", str(dst)], logger)
    logger.log(f"エンドカードを追加 {card_dur}s", stage="3", end_card=end_card)
    return dst, total


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
    end_card = assemble_cfg.get("end_card") or None
    if not end_card:
        out, total = media.assemble(
            clips, dst, xfade, fade_out, width, height, fps,
            music=music,
            keep_clip_audio=bool((config.get("music") or {}).get("keep_clip_audio", False)),
            logger=logger,
            **transition_kwargs(project),
        )
    else:
        out, total = _assemble_with_end_card(
            clips, dst, xfade, fade_out, width, height, fps, end_card, music, project, logger)
    logger.log(
        f"完成: {out} 尺={total:.2f}秒 音声={'あり' if music else 'なし(無音)'}",
        stage="3", output=str(out), duration=round(total, 2), has_music=bool(music),
    )
    return out
