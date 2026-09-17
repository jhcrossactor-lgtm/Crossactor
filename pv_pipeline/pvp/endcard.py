"""闘牛のシルエットを背景に、施設名が現れ、光が走って反射し、最後に沈むエンドカード。

1コマずつ numpy で合成して ffmpeg に流し込む。流れ（既定値、秒）:
  背景が闇から浮かぶ → タイトル2行がゆっくり現れる → 斜めの光がタイトルをなめて反射する
  → 全体がゆっくり沈み、タイトルが「ぎりぎり見える」暗さで止まる
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .overlay import render_text
from .util import RunLogger, ffmpeg_bin


def _ease(x: np.ndarray | float) -> np.ndarray | float:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)  # smoothstep


def _ramp(t: float, t0: float, t1: float) -> float:
    return float(_ease((t - t0) / max(t1 - t0, 1e-6)))


def _text_layer(item: dict, width: int, height: int, work: Path, name: str):
    """文字を全画面サイズのアルファ（0〜1）にして、位置と外接矩形を返す。"""
    png = render_text({**item, "shadow": 0}, width, work / f"{name}.png")
    im = Image.open(png)
    alpha = np.zeros((height, width), dtype=np.float32)
    tw, th = im.size
    cx, cy = float(item.get("x", 0.5)) * width, float(item.get("y", 0.5)) * height
    left, top = round(cx - tw / 2), round(cy - th / 2)
    a = np.asarray(im.getchannel("A"), dtype=np.float32) / 255.0
    ys, xs = slice(max(top, 0), min(top + th, height)), slice(max(left, 0), min(left + tw, width))
    alpha[ys, xs] = a[ys.start - top: ys.stop - top, xs.start - left: xs.stop - left]
    glow = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(radius=max(4, th * 0.12))), dtype=np.float32) / 255.0
    nz = np.argwhere(a > 0.05)
    bbox = (left + nz[:, 1].min(), top + nz[:, 0].min(), left + nz[:, 1].max(), top + nz[:, 0].max())
    return alpha, glow, bbox


def render_bull_shine_card(
    dst: Path,
    cfg: dict,
    background: Path,
    width: int,
    height: int,
    fps: int,
    logger: RunLogger | None = None,
) -> Path:
    duration = float(cfg.get("duration", 9.0))
    tl = {  # タイムライン（秒）
        "bg_in": (0.2, 2.4),
        "title_in": (1.4, 3.4),
        "sub_in": (2.3, 4.2),
        "shine": (4.4, 5.9),
        "dim": (6.2, 8.2),
        **{k: tuple(v) for k, v in (cfg.get("timeline") or {}).items()},
    }
    bg_level = float(cfg.get("bg_level", 0.6))        # 浮かんだ時の背景の明るさ
    bg_dim = float(cfg.get("bg_dim", 0.14))           # 沈んだ後の背景
    text_level = float(cfg.get("text_level", 0.86))   # 通常時の文字の明るさ（光が当たると1.0を超えて輝く）
    text_dim = float(cfg.get("text_dim", 0.26))       # 沈んだ後の文字（ぎりぎり見える）
    rise = float(cfg.get("rise", 0.012)) * height
    gold = np.array(cfg.get("shine_color", [255, 232, 185]), dtype=np.float32) / 255.0

    work = dst.parent / "_endcard"
    work.mkdir(parents=True, exist_ok=True)
    # 背景の位置合わせ：タイトルと角が重ならないよう、縮小・移動できる
    bg_scale = float(cfg.get("bg_scale", 1.0))
    bgx, bgy = (list(cfg.get("bg_offset") or [0.0, 0.0]) + [0.0, 0.0])[:2]
    src = Image.open(background).convert("RGB")
    sw, sh_ = round(width * bg_scale), round(height * bg_scale)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(src.resize((sw, sh_), Image.LANCZOS),
                 (round((width - sw) / 2 + bgx * width), round((height - sh_) / 2 + bgy * height)))
    bg = np.asarray(canvas, dtype=np.float32) / 255.0

    title, sub = cfg["title"], cfg["subtitle"]
    ta, tg, tb = _text_layer(title, width, height, work, "title")
    sa, sg, sb = _text_layer(sub, width, height, work, "subtitle")
    x0, x1 = min(tb[0], sb[0]), max(tb[2], sb[2])
    y0 = min(tb[1], sb[1])

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    slant = 0.45  # 光の帯の傾き
    sigma = max(60.0, (x1 - x0) * float(cfg.get("shine_width", 0.11)))
    shine_gain = float(cfg.get("shine_gain", 1.0))

    cmd = [ffmpeg_bin(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
           "-pix_fmt", "yuv420p", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    frames = round(duration * fps)
    try:
        for i in range(frames):
            t = i / fps
            dim = _ramp(t, *tl["dim"])
            k_bg = bg_level * _ramp(t, *tl["bg_in"]) * (1 - dim) + bg_dim * dim
            frame = bg * k_bg

            # 光の帯：タイトルの左外から右外へ斜めに走る
            sh = (t - tl["shine"][0]) / (tl["shine"][1] - tl["shine"][0])
            band_strength = float(np.sin(np.clip(sh, 0, 1) * np.pi)) if 0 <= sh <= 1 else 0.0
            if band_strength > 0:
                cx = (x0 - 3 * sigma) + (x1 - x0 + 6 * sigma) * float(_ease(sh))
                d = (xx - cx) + slant * (yy - y0)
                band = np.exp(-(d / sigma) ** 2) * band_strength
                # 背景の闘牛の輪郭にも、ごく弱く光がかすめる
                frame = frame + bg * band[..., None] * 0.9 * (1 - dim)
            else:
                band = None

            for alpha, glow, (t0, t1) in ((ta, tg, tl["title_in"]), (sa, sg, tl["sub_in"])):
                a_in = _ramp(t, t0, t1)
                if a_in <= 0:
                    continue
                shift = round(rise * (1 - a_in))
                A = np.roll(alpha, shift, axis=0) * a_in
                G = np.roll(glow, shift, axis=0) * a_in
                level = text_level * (1 - dim) + text_dim * dim
                color = np.ones(3, dtype=np.float32) * level
                frame = frame * (1 - A[..., None]) + color * A[..., None]
                if band is not None:
                    frame = frame + (A * band * 0.9 * shine_gain)[..., None] * gold    # 文字面が金色に光る
                    frame = frame + (G * band * 1.8 * shine_gain)[..., None] * gold    # にじむ反射光（ブルーム）

            out = (np.clip(frame, 0, 1) * 255).astype(np.uint8)
            proc.stdin.write(out.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(f"エンドカードの書き出しに失敗:\n{err[-1500:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    if logger:
        logger.log(f"エンドカード（闘牛・光の反射）を作成 {duration}s -> {dst}", timeline=tl)
    return dst
