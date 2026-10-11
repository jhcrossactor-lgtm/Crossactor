# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow>=10.4", "numpy"]
# ///
"""ChatGPT などで描いた差分絵を、マスクの内側だけ source.png に合成して variants/ 用の PNG を作る。

build-sprites.py は「マスクの外側が 1 ピクセルでも変わった画像」を拒否する。
ChatGPT の画像編集は全体を再圧縮・微妙にずらすことが多いので、そのままでは通らない。
このスクリプトで「外側は source.png のまま、内側だけ生成画像」に作り直してから variants/ に置く。

使い方（リポジトリ直下で）:
  uv run tools/merge-variant.py projects/kuro eyes_closed  path/to/chatgpt_output.png
  uv run tools/merge-variant.py projects/kuro mouth_a      path/to/chatgpt_output.png --shift 0 0

  → projects/kuro/variants/<variant>.png を書き出す。続けて
  uv run tools/build-sprites.py projects/kuro

生成画像のサイズが違う場合は source.png のサイズに合わせて拡大縮小する（位置がずれていると
合成後に目や口が二重になるので、その時は --shift dx dy で生成画像を動かして合わせる）。
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

VARIANTS = ("eyes_closed", "eyes_half", "eyes_smile", "mouth_a", "mouth_a_half", "mouth_i", "mouth_o")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="projects/<name>")
    ap.add_argument("variant", choices=VARIANTS)
    ap.add_argument("generated", type=Path, help="ChatGPT が出力した画像")
    ap.add_argument("--shift", nargs=2, type=int, default=(0, 0), metavar=("DX", "DY"), help="生成画像をずらす px（右・下が正）")
    ap.add_argument("--feather", type=int, default=3, help="マスク境界をぼかす px（既定 3）")
    args = ap.parse_args()

    src_path = args.project / "source.png"
    mask_path = args.project / "variant-requests" / args.variant / "mask.png"
    for p in (src_path, mask_path, args.generated):
        if not p.exists():
            print(f"見つからない: {p}", file=sys.stderr)
            return 1

    src = Image.open(src_path).convert("RGBA")
    gen = Image.open(args.generated).convert("RGBA")
    mask_img = Image.open(mask_path).convert("RGBA")
    if mask_img.size != src.size:
        print(f"mask.png のサイズ {mask_img.size} が source.png {src.size} と違う。variant-requests.py を作り直して", file=sys.stderr)
        return 1
    if gen.size != src.size:
        print(f"生成画像 {gen.size} を source.png のサイズ {src.size} に合わせる")
        gen = gen.resize(src.size, Image.LANCZOS)
    dx, dy = args.shift
    if dx or dy:
        shifted = Image.new("RGBA", src.size, (0, 0, 0, 0))
        shifted.paste(gen, (dx, dy))
        gen = shifted

    # mask.png は「透明 = 編集してよい」「不透明 = 守る」。編集可能域を 0..1 の重みにする
    m = np.asarray(mask_img)[:, :, 3].astype(np.float32)
    editable = (m < 128).astype(np.float32)
    if args.feather > 0:
        from PIL import ImageFilter
        e_img = Image.fromarray((editable * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(args.feather))
        # 境界の外側（守る側）へは絶対にはみ出さないよう、元の editable で切る
        editable = np.minimum(editable, np.asarray(e_img).astype(np.float32) / 255.0)
    w = editable[:, :, None]

    s = np.asarray(src).astype(np.float32)
    g = np.asarray(gen).astype(np.float32)
    out = s * (1 - w) + g * w
    out_img = Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGBA")

    # 守る側は完全に一致させる（丸め誤差も残さない）
    protected = (m >= 128)
    out_arr = np.asarray(out_img).copy()
    out_arr[protected] = np.asarray(src)[protected]
    out_img = Image.fromarray(out_arr, "RGBA")

    dest_dir = args.project / "variants"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"{args.variant}.png"
    out_img.save(dest)
    changed = int((np.abs(out_arr.astype(np.int16) - np.asarray(src).astype(np.int16)).sum(axis=2) > 0).sum())
    print(f"書き出し: {dest}  （変更ピクセル {changed} / 編集可能域 {int((m < 128).sum())}）")
    print("次: uv run tools/build-sprites.py", args.project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
