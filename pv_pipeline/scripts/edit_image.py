"""承認済みの画像を部分的に直すための単発の画像編集（照明・不要物の差し替えなど）。

プロンプトは logs/prompts/ に残し、元の画像は stage1/_backup/ に退避してから上書きする。

  python scripts/edit_image.py --cut 03 --label remove_yogibo --prompt-file p.txt --ref input:ref_IMG_5654.jpg
  python scripts/edit_image.py --target input/_endcard_canvas.png --out input/endcard_bull_lit.png --prompt-file p.txt
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pvp.providers.factory import build_image_provider  # noqa: E402
from pvp.util import RunLogger, load_dotenv, load_project  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--cut", help="stage1/cutNN.png を編集対象にする")
    ap.add_argument("--target", help="編集対象（プロジェクト相対 or 絶対パス）")
    ap.add_argument("--out", help="出力先。省略時は編集対象を上書き")
    ap.add_argument("--label", default="edit")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--ref", action="append", default=[], help="参考画像。input:xxx / stage1:NN / パス")
    args = ap.parse_args()

    import os

    root = Path(args.project or os.environ.get("PVP_PROJECT") or HERE / "projects/villa_test")
    load_dotenv([root / ".env", HERE / ".env", HERE.parent / ".env"])
    pr = load_project(root)

    def resolve(spec: str) -> Path:
        if spec.startswith("input:"):
            return pr.input_dir / spec.split(":", 1)[1]
        if spec.startswith("stage1:"):
            return pr.stage1_dir / f"cut{spec.split(':', 1)[1].zfill(2)}.png"
        p = Path(spec)
        return p if p.is_absolute() else pr.root / p

    if args.cut:
        target = pr.stage1_dir / f"cut{args.cut.zfill(2)}.png"
    elif args.target:
        target = resolve(args.target)
    else:
        raise SystemExit("--cut か --target を指定すること")
    out = resolve(args.out) if args.out else target

    source = target
    if out == target:
        backup = pr.stage1_dir / "_backup" / f"{target.stem}_before_{args.label}_{time.strftime('%H%M%S')}.png"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        source = backup

    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    refs = [resolve(r) for r in args.ref]
    logger = RunLogger(pr.log_dir, f"edit_{args.label}")
    cut_id = (args.cut or "xx").zfill(2)
    logger.save_prompt(cut_id, f"edit_{args.label}", prompt,
                       {"edit_target": source.name, "references": [r.name for r in refs], "out": str(out)})
    build_image_provider(pr.config).edit(prompt, [source] + refs, out, logger, cut_id)
    print(f"出力: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
