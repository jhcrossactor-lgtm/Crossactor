"""Audiveris のページごとの .mxl を継ぎ合わせて1つの総譜（1楽章分）にする。

- 各ページに audiveris_fix の補正（抜け小節・はみ出し・短い小節・任意でフェルマータ除去）をかけてから並べる
- ページによって段数が違う（例: 楽章の頭だけ5楽器）ときは、段→楽器の対応を指定する。
  そのページに無い楽器は全休符で埋める
- 読み取れなかったページは「GAP:小節数」で指定すると、その数だけ全休符の小節を入れて
  先頭パートに目印の文字を付ける（後で手入力する場所）

使い方:
  py merge_pages.py <出力.musicxml> --names "Tp 1,Tp 2,...,Tuba" [--title 題名] [--drop-fermatas]
      page_001.mxl  page_002.mxl  page_013.mxl@4,5,6,7,9  GAP:14 ...
  @ の後ろは「そのページの上から順の段が、--names の何番目（1始まり）か」
"""
import argparse
import copy

from music21 import clef, converter, expressions, metadata, meter, note, stream

import audiveris_fix as fix

BASS_HINTS = ("Tb", "Tuba", "Trombone", "Euph", "Bass", "Fg", "Vc", "Cb")


def default_clef(name):
    return clef.BassClef() if any(h in name for h in BASS_HINTS) else clef.TrebleClef()


def load_page(path, drop_fermatas, meter_state, names, mapping):
    score = converter.parse(path)
    parts = list(score.parts)
    slots = [int(s) - 1 for s in mapping.split(",")] if mapping else list(range(len(parts)))
    if len(slots) != len(parts):
        raise SystemExit(f"段数 {len(parts)} と対応指定 {len(slots)} が合わない: {path}")
    for p, s in zip(parts, slots):  # ログを楽器名で出すため先に名前を付ける
        p.partName = names[s] if s < len(names) else f"段{s + 1}"
    if drop_fermatas:
        for name, num in fix.drop_fermatas(score):
            print(f"    {name} {num}小節目: フェルマータを外した")
    for name, missing in fix.fill_missing_measures(score):
        print(f"    {name}: 小節 {missing} が無いので全休符で補った")
    for num, ts in fix.fit_meter_to_content(score, meter_state):
        print(f"    {num}小節目: 中身の長さに合わせて拍子を {ts} にした")
    for name, num in fix.clear_broken_tuplets(score):
        print(f"    {name} {num}小節目: 連符が崩れていたので全休符にした（手入力）")
    fix.trim_long_measures(score)
    fix.fill_short_measures(score)
    return [list(p.getElementsByClass(stream.Measure)) for p in score.parts], slots


def rest_measure(ql, ref=None):
    m = stream.Measure()
    if ref is not None:  # 拍子・調の変わり目は休みのパートにも写す
        for cls in (meter.TimeSignature,):
            for e in ref.getElementsByClass(cls):
                m.insert(0, copy.deepcopy(e))
        if ref.keySignature is not None:
            m.insert(0, copy.deepcopy(ref.keySignature))
    m.append(note.Rest(quarterLength=ql))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dst")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--names", required=True)
    ap.add_argument("--title")
    ap.add_argument("--drop-fermatas", action="store_true")
    args = ap.parse_args()

    names = [n.strip() for n in args.names.split(",")]
    cols = [[] for _ in names]  # 楽器ごとの小節列
    bar_ql = 4.0
    meter_state = {}  # 拍子をページ間で引き継ぐ

    for spec in args.inputs:
        if spec.startswith("GAP:"):
            n = int(spec[4:])
            print(f"  [読み取り失敗] 全休符 {n} 小節を挿入")
            for i, col in enumerate(cols):
                for k in range(n):
                    m = rest_measure(bar_ql)
                    if i == 0 and k == 0:
                        m.insert(0, expressions.TextExpression("★ここから読み取り失敗ページ（手入力）"))
                    col.append(m)
            continue
        path, _, mapping = spec.partition("@")
        print(f"  {path}")
        page, slots = load_page(path, args.drop_fermatas, meter_state, names, mapping)
        n =max(len(ms) for ms in page)
        start = len(cols[0]) + 1
        print(f"    {len(page)} 段 × {n} 小節 → 楽章の {start}〜{start + n - 1} 小節目"
              f"（上のログの小節番号はページ内の番号。楽章では +{start - 1}）")
        ref = page[0]
        for k in range(n):
            r = ref[k] if k < len(ref) else None
            if r is not None and r.duration.quarterLength:
                bar_ql = r.duration.quarterLength
            for i, col in enumerate(cols):
                if i in slots and k < len(page[slots.index(i)]):
                    col.append(copy.deepcopy(page[slots.index(i)][k]))
                else:
                    col.append(rest_measure(bar_ql, r))

    out = stream.Score()
    out.metadata = metadata.Metadata(title=args.title or "", composer="")
    for name, col in zip(names, cols):
        p = stream.Part()
        p.partName = p.partAbbreviation = name
        offset = 0.0
        for num, m in enumerate(col, 1):
            m.number = num
            if num == 1 and not m.getElementsByClass(clef.Clef):
                m.insert(0, default_clef(name))
            p.insert(offset, m)
            offset += m.duration.quarterLength or bar_ql
        out.insert(0, p)
    out.write("musicxml", fp=args.dst)
    print(f"→ {args.dst}（{len(cols[0])} 小節）")


if __name__ == "__main__":
    main()
