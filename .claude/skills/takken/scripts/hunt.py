# -*- coding: utf-8 -*-
"""照合結果CSVの「＊要確認」を全ページ横断で探す。

PDF と OFF（印刷ページ→PDFページのオフセット。宅建業法=11 / 民法等=15）と
QUERIES（探す文言のリスト）を書き換えて実行する。CLI でも上書きできる：

    python hunt.py --pdf "G:/.../26宅建_基本テキスト(宅建業法).pdf" --offset 11
    python hunt.py --queries queries.txt      # ラベル|文言|正規表現（正規表現は省略可）

正規化は add_markers.py と共有する（_norm.py）。NFKC はかけない。
追加で当てたい文字幅ちがいは --queries の正規表現欄に書く（診断専用）。
"""
import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).parent))
from _norm import norm  # noqa: E402

# --- ここを書き換えて使う ---------------------------------------------------
PDF = Path(r"G:\google drive_jh\宅建テキスト\26宅建_基本テキスト(宅建業法).pdf")
OFF = 11
QUERIES = [
    # (ラベル, 探す文言, 追加で当てる正規表現 or None)
    # ("6-1 / 指示154", "5％以下", r"[0-9]+\s*[%％]\s*以下"),
]
# ---------------------------------------------------------------------------



def build_pagemap(doc, off):
    """印刷ページ番号 -> PDFインデックス"""
    pmap = {}
    for i in range(doc.page_count):
        h = doc[i].rect.height
        nums = [w[4] for w in doc[i].get_text("words") if w[1] > h - 60 and w[4].isdigit()]
        if nums and abs(i - int(nums[0]) - (off - 1)) <= 3:
            pmap.setdefault(int(nums[0]), i)
    return pmap


def best_windows(pages, nq, topn=4):
    out = []
    L = len(nq)
    for i, v in enumerate(pages):
        if not v:
            continue
        if nq in v:
            out.append((1.0, i, v.find(nq)))
            continue
        b = (0.0, -1)
        step = 1 if L < 40 else 3
        for s in range(0, max(1, len(v) - L + 1), step):
            r = difflib.SequenceMatcher(None, nq, v[s:s + L], autojunk=False).ratio()
            if r > b[0]:
                b = (r, s)
        if b[0] > 0.45:
            out.append((b[0], i, b[1]))
    out.sort(reverse=True)
    return out[:topn]


def show(pages, raw, printed, label, q, extra_regex=None):
    print("=" * 78)
    print(f"■ {label}")
    print(f"  原文候補を探す文言: {q}")
    nq = norm(q)
    hits = best_windows(pages, nq)
    if not hits:
        print("  → 全ページで類似箇所なし")
    for score, i, s in hits:
        snip = pages[i][max(0, s - 15): s + len(nq) + 25]
        tag = "完全一致" if score == 1.0 else f"類似{score:.2f}"
        print(f"  [{tag}] 印刷p{printed(i)} (PDF {i + 1}) … {snip}")
    if extra_regex:
        # 文字幅ちがい（5% と ５％、1か月 と 1ヶ月）を拾うための逃げ道。
        # 照合本体には NFKC をかけない。ここは所在を突き止める診断専用。
        print(f"  --- 正規表現 {extra_regex} ---")
        pat = re.compile(extra_regex)
        for i, t in enumerate(raw):
            folded = unicodedata.normalize("NFKC", t)
            for m in pat.finditer(folded):
                a, b = max(0, m.start() - 30), m.end() + 30
                line = folded[a:b].replace("\n", " ")
                print(f"      印刷p{printed(i)} (PDF {i + 1}): …{line}…")


def load_queries(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 2:
            continue
        out.append((parts[0], parts[1], parts[2] if len(parts) > 2 and parts[2].strip() else None))
    return out


def main():
    ap = argparse.ArgumentParser(description="＊要確認 の文言を全ページ横断で探す")
    ap.add_argument("--pdf", default=str(PDF))
    ap.add_argument("--offset", type=int, default=OFF)
    ap.add_argument("--queries", help="ラベル|文言|正規表現 の行を並べたファイル")
    a = ap.parse_args()

    queries = load_queries(a.queries) if a.queries else QUERIES
    if not queries:
        ap.error("探す文言が無い。--queries を渡すか、このファイルの QUERIES を書き換えろ")

    doc = fitz.open(a.pdf)
    raw = [doc[i].get_text() for i in range(doc.page_count)]
    pages = [norm(t) for t in raw]
    pmap = build_pagemap(doc, a.offset)
    inv = {v: k for k, v in pmap.items()}

    def printed(i):
        return inv.get(i, i - a.offset + 1)

    for lbl, q, rx in queries:
        show(pages, raw, printed, lbl, q, rx)


if __name__ == "__main__":
    main()
