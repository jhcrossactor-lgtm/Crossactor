"""Audiveris の MusicXML を MuseScore が開ける形に整える。

- パートによって小節番号が抜けることがある（例: Tuba だけ4小節目が無い）。
  MuseScore はパート間で小節数が違う MusicXML を開けない（終了コード 1320）ので、
  全パートの小節番号の和集合に揃え、抜けた小節は全休符で補う
- パート名（Audiveris は "Voice" などにする）を指定された名前に付け替える

使い方: py audiveris_fix.py <入力.mxl> <出力.musicxml> [--names "Tp 1,Tp 2,..."] [--drop-fermatas]
"""
import argparse
import copy

from music21 import converter, meter, note, stream


def fill_missing_measures(score) -> list:
    parts = list(score.parts)
    numbers = sorted({m.number for p in parts for m in p.getElementsByClass(stream.Measure)})
    report = []
    for p in parts:
        have = {m.number: m for m in p.getElementsByClass(stream.Measure)}
        missing = [n for n in numbers if n not in have]
        if not missing:
            continue
        report.append((p.partName, missing))
        # 小節を作り直して並べ直す（offset はパートの先頭から詰め直す）
        ts = p.recurse().getElementsByClass(meter.TimeSignature).first()
        bar_ql = ts.barDuration.quarterLength if ts else 4.0
        rebuilt = []
        for n in numbers:
            if n in have:
                rebuilt.append(have[n])
            else:
                m = stream.Measure(number=n)
                m.append(note.Rest(quarterLength=bar_ql))
                rebuilt.append(m)
        for m in list(p.getElementsByClass(stream.Measure)):
            p.remove(m)
        offset = 0.0
        for m in rebuilt:
            p.insert(offset, m)
            offset += m.duration.quarterLength if m.duration.quarterLength else bar_ql
    return report


PLAUSIBLE = {"2/4", "3/4", "4/4", "5/4", "6/4", "3/8", "6/8", "9/8", "12/8", "5/8", "7/8"}


def _ts_for(ql, prefer_eighths=False):
    """小節の長さ（4分音符単位）→ 拍子。半端なら x/8、整数なら x/4（今が x/8 系なら x/8 を優先）。
    楽譜でまず見ない拍子（13/8 など。読み違いの産物）は None"""
    if abs(ql * 2 - round(ql * 2)) > 1e-6:
        return None
    eighths = f"{int(round(ql * 2))}/8"
    quarters = f"{int(round(ql))}/4" if abs(ql - round(ql)) < 1e-6 else None
    for cand in ([eighths, quarters] if prefer_eighths else [quarters, eighths]):
        if cand in PLAUSIBLE:
            return meter.TimeSignature(cand)
    return None


def fit_meter_to_content(score, state=None) -> list:
    """拍子記号の読み落とし対策（例: 2/4→9/8 の 9/8 を読み落とすと、後ろの小節が全部 2/4 で切り詰められる）。
    小節ごとに、音のあるパートの小節の長さで最も多いものを「その小節の長さ」とみなし、
    今の拍子と違えばその小節に拍子記号を入れ直す。trim / fill の前に呼ぶ。"""
    from collections import Counter
    parts = [list(p.getElementsByClass(stream.Measure)) for p in score.parts]
    n = max(len(ms) for ms in parts)
    # state: ページをまたいで拍子を引き継ぐための dict（{"cur": 小節の長さ, "eighths": x/8系か}）
    state = state if state is not None else {}
    cur = state.get("cur")
    eighths = state.get("eighths", False)
    changes = []
    for k in range(n):
        ms = [ms[k] for ms in parts if k < len(ms)]
        for m in ms:  # 読み取った拍子記号があれば一旦それを今の拍子にする
            if m.timeSignature is not None:
                cur = m.timeSignature.barDuration.quarterLength
                eighths = m.timeSignature.denominator == 8
                break
        lens = [round(m.duration.quarterLength * 4) / 4 for m in ms
                if m.recurse().notes and m.duration.quarterLength]
        if not lens:
            continue
        (ql, votes), = Counter(lens).most_common(1)
        if cur is not None and abs(ql - cur) < 1e-6:
            continue
        # 多数決が弱いときは読み違いとみなして今の拍子のまま（はみ出しは後で切る）
        if cur is not None and (votes < 3 or votes < 0.6 * len(lens)):
            continue
        # 今より短い小節は音の読み落としでも起きるので、ほぼ全員一致のときだけ（短いままでも休符で埋まり、音は消えない）
        if cur is not None and ql < cur and votes < 0.8 * len(lens):
            continue
        ts = _ts_for(ql, eighths)
        if ts is None:
            continue
        for m in ms:
            for old in list(m.getElementsByClass(meter.TimeSignature)):
                m.remove(old)
            m.insert(0, copy.deepcopy(ts))
        changes.append((ms[0].number, ts.ratioString))
        cur = ql
        eighths = ts.denominator == 8
    state["cur"], state["eighths"] = cur, eighths
    return changes


def clear_broken_tuplets(score) -> list:
    """連符の一部を読み落とした声部（例: 3連符が2音しかない）は、小節の長さが半端な分数になり
    休符で埋めても MuseScore が開かない（Incomplete measure）。その小節のその声部を全休符にする。
    判定: 連続する連符の音のまとまりが、16分音符の格子（0.25拍）で終わっていなければ崩れている"""
    def on_grid(x):
        return abs(x * 4 - round(x * 4)) < 1e-4

    cleared = []
    for p in score.parts:
        ts = None
        for m in p.getElementsByClass(stream.Measure):
            ts = m.timeSignature or ts
            bar = ts.barDuration.quarterLength if ts else 4.0
            for v in (list(m.voices) or [m]):
                items = list(v.notesAndRests)
                broken = False
                run_end = None
                for n in items:
                    if n.duration.tuplets:
                        run_end = n.offset + n.quarterLength
                    elif run_end is not None:
                        broken |= not on_grid(run_end)
                        run_end = None
                if run_end is not None:
                    broken |= not on_grid(run_end)
                if not broken:
                    continue
                for n in items:
                    v.remove(n)
                if v is m:
                    m.append(note.Rest(quarterLength=bar))
                else:
                    r = note.Rest(quarterLength=bar)
                    r.style.hideObjectOnPrint = True
                    v.insert(0, r)
                cleared.append((p.partName, m.number))
    return cleared


def trim_long_measures(score) -> int:
    """拍子より長い小節の、はみ出した音を切り落とす（小節線をまたぐ音は短くする）。
    そのままだと書き出し時に music21 が余りを次の小節に送り、小節が1つ増えてパート間でずれる。"""
    count = 0
    for p in score.parts:
        ts = None
        for m in p.getElementsByClass(stream.Measure):
            ts = m.timeSignature or ts
            bar = ts.barDuration.quarterLength if ts else 4.0
            targets = list(m.voices) if m.voices else [m]
            cut = False
            for v in targets:
                for n in list(v.notesAndRests):
                    if n.offset >= bar - 1e-6:
                        v.remove(n)
                        cut = True
                    elif n.offset + n.quarterLength > bar + 1e-6:
                        n.quarterLength = bar - n.offset
                        cut = True
            if cut:
                count += 1
    return count


def fill_short_measures(score) -> int:
    """拍子より短い小節の末尾に休符を足す。MuseScore 4 の CLI は短い小節（Incomplete measure）が
    1つでもあるとファイルを開かない（終了コード 1320）。中身が空の小節も全休符にする。"""
    count = 0
    for p in score.parts:
        ts = None
        for m in p.getElementsByClass(stream.Measure):
            ts = m.timeSignature or ts
            bar = ts.barDuration.quarterLength if ts else 4.0
            targets = list(m.voices) if m.voices else [m]
            for v in targets:
                filled = max((n.offset + n.quarterLength for n in v.notesAndRests), default=0.0)
                if filled < bar - 1e-6:
                    r = note.Rest(quarterLength=bar - filled)
                    if v is not m and filled > 0:
                        r.style.hideObjectOnPrint = True  # 2声目の埋め草は表示しない
                    v.insert(filled, r)
                    count += 1
    return count


def drop_fermatas(score) -> list:
    """フェルマータを外す。Audiveris は松葉（< >）をフェルマータと読み違えることがある。
    本物のフェルマータも消えるので、外した位置を返して手で戻せるようにする。"""
    from music21 import expressions
    removed = []
    for p in score.parts:
        for n in p.recurse().notesAndRests:
            for e in [e for e in n.expressions if isinstance(e, expressions.Fermata)]:
                n.expressions.remove(e)
                removed.append((p.partName, n.measureNumber))
    return removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--names", help="カンマ区切りのパート名（上から順）")
    ap.add_argument("--drop-fermatas", action="store_true",
                    help="フェルマータを外す（松葉の読み違い対策。外した位置を表示する）")
    args = ap.parse_args()

    score = converter.parse(args.src)
    if args.names:  # 先に付けておくと、以降のログが楽器名で出る
        from music21 import instrument
        for p, name in zip(score.parts, [n.strip() for n in args.names.split(",")]):
            p.partName = name
            p.partAbbreviation = name
            for inst in p.recurse().getElementsByClass(instrument.Instrument):
                inst.partName = name
                inst.partAbbreviation = name
    if args.drop_fermatas:
        for name, num in drop_fermatas(score):
            print(f"  {name} {num}小節目: フェルマータを外した（本物なら手で戻す）")
    for name, missing in fill_missing_measures(score):
        print(f"  {name}: 小節 {missing} が無いので全休符で補った")
    for num, ts in fit_meter_to_content(score):
        print(f"  {num}小節目: 中身の長さに合わせて拍子を {ts} にした")
    for name, num in clear_broken_tuplets(score):
        print(f"  {name} {num}小節目: 連符が崩れていたので全休符にした（手入力）")
    print(f"  拍子より長い小節のはみ出しを切った: {trim_long_measures(score)} 小節")
    print(f"  拍子より短い小節を休符で埋めた: {fill_short_measures(score)} か所")
    score.write("musicxml", fp=args.dst)
    print(f"→ {args.dst}")


if __name__ == "__main__":
    main()
