"""動画に文字を重ねる（キャッチコピー・施設名・エンドカード）。

文字を画像生成・動画生成に描かせると、動きの中で崩れたり揺れたりする。
ここでは Pillow で文字を透過PNGに描き、ffmpeg でフェードイン（わずかに浮き上がる）させて重ねる。
字間（tracking）は1文字ずつ配置して付ける。
"""

from __future__ import annotations

from pathlib import Path

from .util import RunLogger, ffmpeg_bin, run_cmd

FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path.home() / "AppData/Local/Microsoft/Windows/Fonts"]


def _font_path(name: str) -> Path:
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    for d in FONT_DIRS:
        if (d / name).exists():
            return d / name
    raise FileNotFoundError(f"フォントが見つからない: {name}")


def render_text(item: dict, width: int, out: Path) -> Path:
    """1行の文字を透過PNGに描く。size は出力幅に対する文字高さの比（例 0.045）。"""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    text = str(item["text"])
    size_px = max(8, round(float(item.get("size", 0.04)) * width))
    font = ImageFont.truetype(str(_font_path(item.get("font", "KozMinPro-Light.otf"))), size_px)
    tracking = float(item.get("tracking", 0.0)) * size_px  # em 単位
    color = tuple(item.get("color", [255, 255, 255]))

    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + tracking * max(len(text) - 1, 0)
    ascent, descent = font.getmetrics()
    pad = round(size_px * 0.6)
    w, h = round(total) + pad * 2, ascent + descent + pad * 2

    glyphs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(glyphs)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=font, fill=color + (255,))
        x += cw + tracking

    # 背景になじませるための、ごく薄い影
    shadow_alpha = int(float(item.get("shadow", 0.35)) * 255)
    if shadow_alpha > 0:
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow.putalpha(glyphs.getchannel("A").point(lambda a: a * shadow_alpha // 255))
        shadow = shadow.filter(ImageFilter.GaussianBlur(size_px * 0.12))
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(glyphs)
        glyphs = canvas

    out.parent.mkdir(parents=True, exist_ok=True)
    glyphs.save(out)
    return out


def apply_overlays(
    src: Path,
    dst: Path,
    overlays: list[dict],
    width: int,
    height: int,
    fps: int,
    duration: float,
    logger: RunLogger | None = None,
) -> Path:
    """src に文字を順にフェードインさせて重ね、dst に書き出す。

    各項目: text, font, size, x, y（0〜1。anchor の位置）, anchor（left / center）,
            start（秒）, fade（秒）, rise（浮き上がり量。出力高さに対する比）, fade_out（秒、任意）
    """
    work = dst.parent / "_overlay"
    inputs = ["-i", str(src)]
    chains = []
    last = "[0:v]"
    for i, item in enumerate(overlays, start=1):
        png = render_text(item, width, work / f"{dst.stem}_{i}.png")
        from PIL import Image

        tw, th = Image.open(png).size
        inputs += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(png)]
        start = float(item.get("start", 0.0))
        fade = float(item.get("fade", 1.5))
        rise = float(item.get("rise", 0.012)) * height
        ax = float(item.get("x", 0.5)) * width
        ay = float(item.get("y", 0.5)) * height
        if item.get("anchor", "left") == "center":
            left = ax - tw / 2
        else:
            # 描画時に付けた左余白（文字高さの0.6倍）を差し引き、文字の左端を x に合わせる
            left = ax - round(float(item.get("size", 0.04)) * width * 0.6)
        top = ay - th / 2
        prog = f"min(max((t-{start})/{fade}\\,0)\\,1)"
        ease = f"(1-pow(1-{prog}\\,3))"  # ease-out
        fades = f"fade=in:st={start}:d={fade}:alpha=1"
        if item.get("fade_out"):
            fo = float(item["fade_out"])
            fades += f",fade=out:st={duration - fo}:d={fo}:alpha=1"
        chains.append(f"[{i}:v]format=rgba,{fades}[t{i}]")
        chains.append(
            f"{last}[t{i}]overlay=x={left:.1f}:y='{top:.1f}+{rise:.1f}*(1-{ease})':"
            f"shortest=1:format=auto[v{i}]"
        )
        last = f"[v{i}]"
    chains.append(f"{last}fps={fps},format=yuv420p[vout]")
    cmd = [ffmpeg_bin(), "-y"] + inputs + [
        "-filter_complex", ";".join(chains), "-map", "[vout]", "-an",
        "-t", f"{duration:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "slow", str(dst),
    ]
    if logger:
        logger.log(f"文字を重ねる: {[o['text'] for o in overlays]}", overlays=overlays)
    run_cmd(cmd, logger)
    return dst


def black_card(
    dst: Path,
    overlays: list[dict],
    width: int,
    height: int,
    fps: int,
    duration: float,
    logger: RunLogger | None = None,
) -> Path:
    """黒一色の背景に文字を重ねたエンドカードを作る。"""
    base = dst.parent / "_overlay" / f"{dst.stem}_black.mp4"
    base.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([ffmpeg_bin(), "-y", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
             "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(base)], logger)
    return apply_overlays(base, dst, overlays, width, height, fps, duration, logger)
