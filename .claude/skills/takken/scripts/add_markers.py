"""音声講義で指示されたマーカー箇所を、テキストPDFにハイライト注釈として追加する。

marks_*.txt の各行「印刷ページ|文言」を読み、該当ページ（±1ページ）の本文から
文言を探して黄色マーカーを引く。見つからない行はレポートに「＊要確認」と残す。
"""
import argparse
import csv
import difflib
import json
import os
import re
from pathlib import Path

import fitz

# (marks file, skip file, source pdf, output pdf, 番号が読めないページ用の予備オフセット)
# 作業フォルダに jobs.json があればそちらを優先する。
DEFAULT_JOBS = [
    ("marks_minpo.txt", "skip_minpo.txt", "26宅建_テキスト(民法等)完版.pdf", "26宅建_テキスト(民法等)完版_マーカー版.pdf", 15),
    ("marks_gyoho.txt", "skip_gyoho.txt", "26宅建_基本テキスト(宅建業法).pdf", "26宅建_基本テキスト(宅建業法)_マーカー版.pdf", 11),
]
YELLOW = (1.0, 0.93, 0.2)
RED = (0.85, 0.05, 0.05)
# 音声由来の表記ゆれを吸収する
VARIANTS = {"脅迫": "強迫", "帰す": "帰す", "関わらず": "かかわらず", "合わせて": "併せて"}
DROP = re.compile(r"[\s　、。，．,.「」『』（）()・:：;；…\-－―ー〜～⇨→]")


def norm(s):
    for a, b in VARIANTS.items():
        s = s.replace(a, b)
    return DROP.sub("", s)


def page_chars(page):
    """ページの文字を (正規化後の文字, bbox) の列にする。"""
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    c = norm(ch["c"])
                    if c:
                        out.append((c, fitz.Rect(ch["bbox"]), id(ln)))
    return out


def find(chars, q):
    text = "".join(c for c, _, _ in chars)
    i = text.find(q)
    if i >= 0:
        return i, i + len(q), 1.0
    if len(q) < 6:
        return None
    # 近似一致: 同じ長さの窓をずらして最も似ている箇所
    best = (0.0, -1)
    L = len(q)
    for s in range(0, max(1, len(text) - L + 1)):
        r = difflib.SequenceMatcher(None, q, text[s:s + L], autojunk=False).ratio()
        if r > best[0]:
            best = (r, s)
    if best[0] < 0.75:
        return None
    # 窓の端のはみ出しを削り、実際に一致した文字の範囲だけにする
    s = best[1]
    blocks = [m for m in difflib.SequenceMatcher(None, q, text[s:s + L], autojunk=False).get_matching_blocks() if m.size >= 2]
    return s + blocks[0].b, s + blocks[-1].b + blocks[-1].size, best[0]


def highlight(page, chars, a, b):
    lines = {}
    for c, r, lid in chars[a:b]:
        lines.setdefault(lid, fitz.Rect(r)).include_rect(r)
    for r in lines.values():
        annot = page.add_highlight_annot(r)
        annot.set_colors(stroke=YELLOW)
        annot.update()


def mark_skip(page, label):
    """「出ない・飛ばす」と言われたページの右上に赤い×と範囲ラベルを付ける。"""
    w = page.rect.width
    box = fitz.Rect(w - 48, 6, w - 14, 40)
    for a, b in ((box.tl, box.br), (box.tr, box.bl)):
        ln = page.add_line_annot(a, b)
        ln.set_colors(stroke=RED)
        ln.set_border(width=4)
        ln.update()
    if label:
        t = page.add_freetext_annot(fitz.Rect(w - 250, 14, w - 52, 34), f"{label}のみ",
                                    fontsize=9, fontname="japan", text_color=RED, align=2)
        t.update()


def page_map(doc, off):
    """各ページ下端の印刷ペーズ番号を読み、印刷ページ→PDFページ(0始まり)の対応表を作る。
    章扉にはペーズ番号が無く、章ごとにずれ幅が変わるため固定オフセットは使えない。"""
    table = {}
    for i in range(doc.page_count):
        h = doc[i].rect.height
        nums = [w[4] for w in doc[i].get_text("words") if w[1] > h - 60 and w[4].isdigit()]
        # 目次などの数字を拾わないよう、想定のずれ幅から大きく外れる番号は捨てる
        if nums and abs(i - int(nums[0]) - (off - 1)) <= 3:
            table.setdefault(int(nums[0]), i)
    return table


def run(HERE, SRC, JOBS):
    report = []
    skips = []
    for marks, skipf, src, dst, off in JOBS:
        doc = fitz.open(SRC / src)
        cache = {}
        done = set()
        pmap = page_map(doc, off)
        to_idx = lambda p: pmap.get(p, p + off - 1)
        for raw in (HERE / marks).read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.startswith("#"):
                section = raw.lstrip("# ").strip() if raw.startswith("#") else ""
                if section:
                    cur = section
                continue
            p, _, phrase = raw.partition("|")
            if not p.strip().isdigit() or not phrase.strip():
                continue  # 「なし」など形式外の行
            p = int(p)
            q = norm(phrase)
            if (p, q) in done:
                continue
            done.add((p, q))
            hit = None
            for cand in (p, p + 1, p - 1):
                idx = to_idx(cand)
                if not 0 <= idx < doc.page_count:
                    continue
                if idx not in cache:
                    cache[idx] = page_chars(doc[idx])
                m = find(cache[idx], q)
                if m:
                    hit = (cand, idx, m)
                    break
            if hit:
                cand, idx, (a, b, score) = hit
                highlight(doc[idx], cache[idx], a, b)
                status = "一致" if score == 1.0 else f"近似一致（{score:.2f}）"
                report.append([src, cur, p, cand, status, phrase])
            else:
                report.append([src, cur, p, "", "＊要確認（本文に見つからず）", phrase])
        for raw in (HERE / skipf).read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.startswith("#"):
                continue
            parts = raw.split("|")
            if len(parts) != 4 or not parts[0].strip().isdigit():
                continue  # 「なし」など形式外の行
            p, rng, why, voice = parts
            mark_skip(doc[to_idx(int(p))], "" if rng == "全部" else rng)
            skips.append([src, voice, p, rng, why])
        tmp = HERE / (dst + ".tmp")
        doc.save(tmp, garbage=3, deflate=True)
        doc.close()
        try:
            tmp.replace(HERE / dst)
        except PermissionError:
            print(f"※ {dst} は開かれているため上書きできず、{tmp.name} に保存しました")
    with open(HERE / "マーカー照合結果.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PDF", "音声", "指示ページ", "マーカーを引いたページ", "結果", "文言"])
        w.writerows(report)
    with open(HERE / "飛ばしてよいページ一覧.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PDF", "音声", "印刷ページ", "範囲", "講師の発言要旨"])
        w.writerows(skips)
    ok = sum(1 for r in report if not r[4].startswith("＊"))
    print(f"{ok}/{len(report)} 件マーカー済み")


def load_jobs(work):
    """作業フォルダの jobs.json を読む。無ければ既定の2冊（民法等・宅建業法）を使う。"""
    f = work / "jobs.json"
    if not f.exists():
        return DEFAULT_JOBS
    return [(j["marks"], j["skip"], j["src"], j["dst"], int(j["offset"]))
            for j in json.loads(f.read_text(encoding="utf-8"))]


def main():
    ap = argparse.ArgumentParser(description="marks_*.txt / skip_*.txt をもとにテキストPDFへマーカーを引く")
    ap.add_argument("--work", default=os.environ.get("MARKER_WORK", "."),
                    help="marks_*.txt・skip_*.txt が置かれ、マーカー版PDFとCSVを書き出す作業フォルダ（既定: カレント）")
    ap.add_argument("--src", default=os.environ.get("MARKER_SRC"),
                    help="元PDFが置かれたフォルダ（既定: 環境変数 MARKER_SRC）")
    a = ap.parse_args()
    if not a.src:
        ap.error("元PDFのフォルダを --src か環境変数 MARKER_SRC で指定してください")
    work, src = Path(a.work).expanduser(), Path(a.src).expanduser()
    for d in (work, src):
        if not d.is_dir():
            ap.error(f"フォルダが見つかりません: {d}")
    run(work, src, load_jobs(work))


if __name__ == "__main__":
    main()
