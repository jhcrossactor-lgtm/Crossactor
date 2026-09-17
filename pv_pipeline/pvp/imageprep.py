"""API に渡す前に画像を正規化する。

iPhone 写真などは色モード(CMYK/16bit/RGBA)・EXIF回転・巨大サイズなど、
そのまま送ると弾かれたり向きが狂ったりする要因を抱えている。
ここで全部そろえてから送る。素材ごとの当たり外れを無くすのが目的。
"""

from __future__ import annotations

from pathlib import Path

from .util import RunLogger


def prepare_image(
    src: Path,
    work_dir: Path,
    max_edge: int = 2048,
    logger: RunLogger | None = None,
) -> Path:
    """src を RGB・EXIF回転適用・長辺 max_edge 以下の PNG にして返す。

    変換済みが work_dir にあり、元ファイルより新しければそれを使う。
    """
    from PIL import Image, ImageOps

    work_dir.mkdir(parents=True, exist_ok=True)
    dst = work_dir / f"{src.stem}.png"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst

    with Image.open(src) as im:
        original_mode, original_size = im.mode, im.size
        im = ImageOps.exif_transpose(im) or im   # EXIF の回転を画素に焼き込む
        if im.mode != "RGB":
            im = im.convert("RGB")                 # CMYK / RGBA / 16bit / P → RGB
        w, h = im.size
        scale = max_edge / max(w, h)
        if scale < 1.0:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        im.save(dst, "PNG", optimize=False)

    if logger:
        logger.log(
            f"画像を正規化: {src.name} {original_mode} {original_size[0]}x{original_size[1]}"
            f" -> RGB {im.size[0]}x{im.size[1]} ({dst.name})",
            prepared=str(dst), src=str(src), original_mode=original_mode,
        )
    return dst


def prepare_images(
    images: list[Path],
    work_dir: Path,
    max_edge: int = 2048,
    logger: RunLogger | None = None,
) -> list[Path]:
    return [prepare_image(p, work_dir, max_edge, logger) for p in images]


def describe_image(path: Path) -> str:
    """check コマンド用。開けるか・モード・寸法・EXIF回転の有無を1行で返す。"""
    from PIL import Image

    try:
        with Image.open(path) as im:
            exif = im.getexif()
            orientation = exif.get(0x0112, 1) if exif else 1
            rot = f" EXIF回転={orientation}" if orientation not in (None, 1) else ""
            warn = ""
            if im.mode != "RGB":
                warn += f" ※モード{im.mode}→RGBに変換して送る"
            if max(im.size) > 4096:
                warn += " ※大きいので縮小して送る"
            return f"{im.format} {im.mode} {im.size[0]}x{im.size[1]}{rot}{warn}"
    except Exception as exc:  # 画像として開けない
        return f"NG 画像として開けない: {exc}"
