"""oemer を1ページ分だけ実行するランナー（scan2muse.py からサブプロセスで呼ばれる）。

oemer 0.1.8 には `python -m oemer` 用の __main__ が無いため、oemer.ete.main() を直接呼ぶ。
呼ぶ前に、新しい依存ライブラリとの互換パッチを当てる。

使い方: py oemer_runner.py <画像パス> <出力フォルダ> [--without-deskew]
"""
import os
import sys

import numpy as np


def _patch_find_lines():
    """OpenCV 5 で cv2.HoughLinesP の戻り値が (N,1,4) → (N,4) に変わり、
    oemer.bbox.find_lines が IndexError で落ちる問題への対処。形状に依存しない版に差し替える。"""
    import cv2
    from oemer import bbox, staffline_extraction, symbol_extraction, barline_extraction

    def find_lines(data, min_len=10, max_gap=20):
        assert len(data.shape) == 2, f"{type(data)} {data.shape}"
        lines = cv2.HoughLinesP(data.astype(np.uint8), 1, np.pi / 180, 50, None, min_len, max_gap)
        new_line = []
        if lines is not None:
            for line in np.asarray(lines).reshape(-1, 4):
                top_x, bt_x = sorted((line[0], line[2]))
                top_y, bt_y = sorted((line[1], line[3]))
                new_line.append((top_x, top_y, bt_x, bt_y))
        return new_line

    # 各モジュールが `from oemer.bbox import find_lines` で名前を取り込んでいるため全箇所を差し替える
    for mod in (bbox, staffline_extraction, symbol_extraction, barline_extraction):
        mod.find_lines = find_lines


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    img_path, out_dir = sys.argv[1], sys.argv[2]
    extra = sys.argv[3:]

    os.makedirs(out_dir, exist_ok=True)
    _patch_find_lines()
    from oemer import ete

    sys.argv = ["oemer", img_path, "-o", out_dir, *extra]
    ete.main()


if __name__ == "__main__":
    main()
