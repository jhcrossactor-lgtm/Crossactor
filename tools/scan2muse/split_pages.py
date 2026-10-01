"""スキャンPDFを1ページ1枚のPNGにする（Audiveris 用の前処理）。

- 横長ページ（A3見開き）は左右に2分割する
- 縦長ページはそのまま
- 出力: <出力フォルダ>/page_001.png, page_002.png ...（読む順に連番）

使い方: py split_pages.py <入力.pdf> <出力フォルダ> [--dpi 300] [--pages 1-3]
"""
import argparse
import os

import fitz


def parse_range(s, n):
    if not s:
        return list(range(n))
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += range(int(a) - 1, int(b or a))
    return [i for i in out if 0 <= i < n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pages", help="PDFのページ範囲（例 1-3,5）。省略で全ページ")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    doc = fitz.open(args.pdf)
    k = 0
    for i in parse_range(args.pages, doc.page_count):
        page = doc[i]
        r = page.rect
        if r.width > r.height:  # 見開き → 左右
            clips = [fitz.Rect(r.x0, r.y0, r.x0 + r.width / 2, r.y1),
                     fitz.Rect(r.x0 + r.width / 2, r.y0, r.x1, r.y1)]
        else:
            clips = [r]
        for c in clips:
            k += 1
            pix = page.get_pixmap(dpi=args.dpi, clip=c, colorspace=fitz.csGRAY)
            path = os.path.join(args.out, f"page_{k:03d}.png")
            pix.save(path)
            print(f"PDF p{i + 1} → {os.path.basename(path)} ({pix.width}x{pix.height})")


if __name__ == "__main__":
    main()
