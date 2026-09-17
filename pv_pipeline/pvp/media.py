"""ffmpeg まわりの処理（16:9切り出し・尺そろえ・xfade結合・フェードアウト）。"""

from __future__ import annotations

from pathlib import Path

from .util import (
    RunLogger,
    ffmpeg_bin,
    has_audio_stream,
    probe_duration,
    run_cmd,
)

# 中央を 16:9 で切り出す crop 式。縦横どちらが余っても中央基準で削る。
CENTER_16X9_CROP = (
    "crop="
    "w='floor(min(iw\\,ih*16/9)/2)*2':"
    "h='floor(min(iw*9/16\\,ih)/2)*2':"
    "x='(iw-ow)/2':"
    "y='(ih-oh)/2'"
)


def convert_heic(src: Path, dst: Path) -> Path:
    """HEIC を JPEG に変換する。pillow-heif が要る。"""
    try:
        import pillow_heif
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - 環境依存
        raise SystemExit(
            "HEIC の変換には pillow と pillow-heif が要る: pip install pillow pillow-heif"
        ) from exc

    pillow_heif.register_heif_opener()
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.convert("RGB").save(dst, "JPEG", quality=95)
    return dst


def video_center_16x9(
    src: Path,
    dst: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    logger: RunLogger | None = None,
) -> Path:
    """実写素材（MOV等）の中央を 16:9 で切り出し、指定尺に詰める。AIは使わない。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"{CENTER_16X9_CROP},scale={width}:{height},setsar=1,fps={fps},format=yuv420p"
    cmd = [
        ffmpeg_bin(), "-y",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-crf", "17", "-preset", "slow",
        str(dst),
    ]
    run_cmd(cmd, logger)
    return dst


def still_to_clip(
    src: Path,
    dst: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    logger: RunLogger | None = None,
) -> Path:
    """静止画をそのまま尺分の動画にする（動画APIを使わないドライラン用）。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
    )
    cmd = [
        ffmpeg_bin(), "-y",
        "-loop", "1", "-i", str(src),
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-crf", "17", "-preset", "medium",
        str(dst),
    ]
    run_cmd(cmd, logger)
    return dst


def normalize_clip(
    src: Path,
    dst: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    keep_audio: bool = False,
    logger: RunLogger | None = None,
) -> Path:
    """生成尺がカット定義とズレるので、解像度・fps・尺を強制的にそろえる。

    長い場合は頭から切り、短い場合は最終フレームを複製して埋める。
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_duration = probe_duration(src)
    pad = max(0.0, duration - src_duration)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"
    )
    if pad > 0.01:
        vf += f",tpad=stop_mode=clone:stop_duration={pad + 0.5:.3f}"
    vf += ",format=yuv420p"

    cmd = [ffmpeg_bin(), "-y", "-i", str(src), "-t", f"{duration:.3f}", "-vf", vf]
    if keep_audio and has_audio_stream(src):
        cmd += ["-af", f"apad=pad_dur={pad + 0.5:.3f}", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "slow", str(dst)]
    run_cmd(cmd, logger)
    return dst


def assemble(
    clips: list[Path],
    dst: Path,
    xfade_duration: float,
    fade_out_duration: float,
    width: int,
    height: int,
    fps: int,
    music: Path | None = None,
    keep_clip_audio: bool = False,
    logger: RunLogger | None = None,
) -> tuple[Path, float]:
    """xfade（クロスディゾルブ）で連結し、最後をフェードアウトして書き出す。

    戻り値は (出力パス, 完成尺)。
    """
    if not clips:
        raise RuntimeError("結合するクリップが無い。先に stage2 を回すこと。")
    dst.parent.mkdir(parents=True, exist_ok=True)

    durations = [probe_duration(c) for c in clips]
    inputs: list[str] = []
    for clip in clips:
        inputs += ["-i", str(clip)]

    parts: list[str] = []
    for idx in range(len(clips)):
        parts.append(
            f"[{idx}:v]scale={width}:{height},setsar=1,fps={fps},format=yuv420p[v{idx}]"
        )

    if len(clips) == 1:
        current = "[v0]"
        total = durations[0]
    else:
        current = "[v0]"
        total = durations[0]
        for idx in range(1, len(clips)):
            offset = total - xfade_duration
            label = f"[x{idx}]"
            parts.append(
                f"{current}[v{idx}]xfade=transition=dissolve:"
                f"duration={xfade_duration:.3f}:offset={offset:.3f}{label}"
            )
            current = label
            total = total + durations[idx] - xfade_duration

    if fade_out_duration > 0:
        fade_start = max(0.0, total - fade_out_duration)
        parts.append(
            f"{current}fade=t=out:st={fade_start:.3f}:d={fade_out_duration:.3f}[vout]"
        )
        vout = "[vout]"
    else:
        parts.append(f"{current}null[vout]")
        vout = "[vout]"

    cmd = [ffmpeg_bin(), "-y"] + inputs
    maps = ["-map", vout]

    if music is not None:
        cmd += ["-i", str(music)]
        music_idx = len(clips)
        fade_start = max(0.0, total - fade_out_duration)
        parts.append(
            f"[{music_idx}:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},"
            f"afade=t=in:st=0:d=1.0,"
            f"afade=t=out:st={fade_start:.3f}:d={max(fade_out_duration, 0.1):.3f}[aout]"
        )
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    elif keep_clip_audio:
        audio_inputs = [i for i, c in enumerate(clips) if has_audio_stream(c)]
        if len(audio_inputs) == len(clips):
            chain = "".join(f"[{i}:a]" for i in audio_inputs)
            parts.append(f"{chain}concat=n={len(audio_inputs)}:v=0:a=1[aout]")
            maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
        else:
            maps += ["-an"]
    else:
        maps += ["-an"]

    cmd += ["-filter_complex", ";".join(parts)] + maps
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", str(dst)]
    run_cmd(cmd, logger)
    return dst, total
