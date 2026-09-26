"""prepare_pages.py で整えたページから、各段組の指定番目の譜表（=1楽器）だけを切り出し、
ページごとの1段譜画像にする。

oemer は1段組あたり譜表1本（または2本=ピアノ）しか扱えないため、総譜は楽器ごとに切り出してから読ませる。
出力フォルダは scan2muse.py にそのまま渡せる（"<名前>_p01.png" … を1パートにまとめて読む）。

使い方:
  py extract_staff.py <整えたページのフォルダ> --staves 10 --index 1 --name "Trumpet 1" --out <出力フォルダ>
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from prepare_pages import staff_x_range


def system_x_range(a: np.ndarray, staves, k: int, per_system: int):
    """k 番目の譜表が属する段組の横範囲。同じ段組の譜表は同じ幅なので、
    段組内で幅がしっかり取れた譜表の x0 / x1 の中央値を使う（1本だけ途切れても影響しない）。"""
    s0 = (k // per_system) * per_system
    ranges = [staff_x_range(a, t, b) for t, b, _ in staves[s0:s0 + per_system]]
    widest = max(x1 - x0 for x0, x1 in ranges)
    good = [(x0, x1) for x0, x1 in ranges if x1 - x0 >= widest * 0.8]
    return int(np.median([x0 for x0, _ in good])), int(np.median([x1 for _, x1 in good]))


def cut_strip(a: np.ndarray, staves, k: int, per_system: int) -> np.ndarray:
    """k 番目の譜表を、上下の隣の譜表との中間まで含めて切り出す（隣の音符が写り込まないように）。"""
    top, bot, sp = staves[k]
    sh = bot - top
    up = min(int(sh * 1.5), (top - staves[k - 1][1]) // 2) if k > 0 else int(sh * 1.5)
    dn = min(int(sh * 1.5), (staves[k + 1][0] - bot) // 2) if k + 1 < len(staves) else int(sh * 1.5)
    y0, y1 = max(0, top - up), min(a.shape[0], bot + dn + 1)
    x0, x1 = system_x_range(a, staves, k, per_system)
    strip = a[y0:y1, max(0, x0 - 2):x1 + 2]
    p2, p98 = np.percentile(strip, 2), np.percentile(strip, 98)   # コントラスト伸長
    return np.clip((strip - p2) / max(p98 - p2, 1) * 255.0, 0, 255).astype(np.uint8)


# oemer は入力を 300万〜435万画素に自動でリサイズする（inference.resize_image）。
# 五線の線間隔が 13px 前後のとき最もよく読めるので、線間隔を揃えたうえで
# 白余白を足して画素数をこの範囲に収め、oemer 側で拡大縮小されないようにする。
TARGET_PIXELS = 3_400_000


def stack(strips, scale: float) -> Image.Image:
    """1段ずつ縦に積んでパート譜風のページにする。"""
    ims = [Image.fromarray(s) for s in strips]
    ims = [im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS) for im in ims]
    gap = 80
    W = max(im.width for im in ims) + 120
    H = max(sum(im.height for im in ims) + gap * (len(ims) + 1), int(TARGET_PIXELS / W))
    page = Image.new("L", (W, H), 255)
    y = gap
    for im in ims:
        page.paste(im, (60, y))
        y += im.height + gap
    return page


def main():
    ap = argparse.ArgumentParser(description="整えた総譜ページから1楽器分の譜表を切り出す")
    ap.add_argument("pages", help="prepare_pages.py の出力フォルダ（pNN.png と _layout.json）")
    ap.add_argument("--staves", type=int, required=True, help="1段組あたりの譜表数（楽器数）")
    ap.add_argument("--index", type=int, default=1, help="切り出す譜表の番号（上から1始まり）")
    ap.add_argument("--name", default="Part", help="出力ファイル名の楽器名（scan2muse がパート名判定に使う）")
    ap.add_argument("--out", required=True, help="出力フォルダ")
    ap.add_argument("--target-sp", type=float, default=13.0, help="出力の五線の線間隔 px（oemer は 13px 前後が最良）")
    ap.add_argument("--per-image", type=int, default=3, help="1枚の出力画像にまとめるページ数（少ないほど失敗時の影響が小さい）")
    args = ap.parse_args()

    pages = Path(args.pages)
    layout = json.loads((pages / "_layout.json").read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    skipped, pending, made = [], [], 0

    def flush():
        nonlocal pending, made
        if not pending:
            return
        made += 1
        page = stack([s for _, s in pending], 1.0)
        fname = f"{args.name}_p{made:02d}.png"
        page.save(out / fname)
        print(f"  {'+'.join(n for n, _ in pending)} → {fname} ({page.width}x{page.height})")
        pending = []

    for name, info in sorted(layout.items()):
        staves = [tuple(s) for s in info["staves"]]
        if not staves or len(staves) % args.staves:
            print(f"{name}: 譜表 {len(staves)} 本 — {args.staves} の倍数でないので飛ばす")
            skipped.append(name)
            continue
        a = np.asarray(Image.open(pages / f"{name}.png").convert("L"), np.float32)
        scale = args.target_sp / float(np.median([s[2] for s in staves]))
        for k in range(args.index - 1, len(staves), args.staves):
            strip = Image.fromarray(cut_strip(a, staves, k, args.staves))
            strip = strip.resize((int(strip.width * scale), int(strip.height * scale)), Image.LANCZOS)
            pending.append((name, np.asarray(strip)))
        if len({n for n, _ in pending}) >= args.per_image:
            flush()
    flush()
    if skipped:
        (out / "_skipped.txt").write_text("\n".join(skipped), encoding="utf-8")
        print(f"飛ばしたページ: {skipped}（_skipped.txt）")


if __name__ == "__main__":
    main()
