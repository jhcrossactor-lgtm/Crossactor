"""ファイル名から吹奏楽のパート名を判定・正規化する。

oemer は楽器名を読み取らない（出力は常に "Piano" 1パート）ため、パート名はファイル名から決める。
例: "Clarinet in Bb 2.pdf" → "Cl 2" / "1.Picc..pdf" → "Picc" / "アルトサックス1.pdf" → "A.Sax 1"

判定ルールを増やしたい時は INSTRUMENTS に1行足す。上にあるものほど優先して判定され、
並び順がそのまま総譜のパート順（吹奏楽の標準スコア順）になる。
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from music21 import instrument, interval

# (正規化後の名前, music21 楽器クラス名 or None, [判定用の正規表現...])
# 楽器クラスが None のものは名前だけ付ける（無音程打楽器など、音程・移調を持たせない）。
# 正規表現は NFKC 正規化＋小文字化したファイル名に対して検索する。
INSTRUMENTS = [
    ("Score", None, [r"\bscore\b", r"full ?score", r"conductor", r"スコア", r"総譜"]),
    ("Picc", "Piccolo", [r"picc", r"piccolo", r"ピッコロ"]),
    ("Fl", "Flute", [r"flute", r"\bfl\b", r"^fl(?=[\s.\d]|$)", r"フルート"]),
    ("Ob", "Oboe", [r"oboe", r"\bob\b", r"^ob(?=[\s.\d]|$)", r"オーボエ"]),
    ("E.Hr", "EnglishHorn", [r"english ?horn", r"cor anglais", r"\be\.?\s?hr?\b", r"イングリッシュ", r"コールアングレ"]),
    ("Fg", "Bassoon", [r"bassoon", r"fagott", r"\bfg\b", r"\bbsn\b", r"ファゴット", r"バスーン"]),
    ("E♭Cl", "Clarinet:m3", [r"e[b♭]\s*cl", r"cl\w*\s+in\s+e[b♭]", r"エスクラ", r"e[b♭]\s*クラ"]),
    ("A.Cl", "Clarinet:M-6", [r"alto\s*cl", r"\ba\.\s?cl", r"アルトクラ"]),
    ("B.Cl", "BassClarinet", [r"bass\s*cl", r"\bb\.\s?cl", r"\bbcl\b", r"バスクラ"]),
    ("Cl", "Clarinet", [r"clarinet", r"\bcl\b", r"^cl(?=[\s.\d]|$)", r"cl(?=\s?\d)", r"クラリネット", r"クラ(?!ッシュ)"]),
    ("S.Sax", "SopranoSaxophone", [r"soprano\s*sax", r"\bs\.\s?sax", r"ソプラノサックス", r"ソプラノ"]),
    ("A.Sax", "AltoSaxophone", [r"alto\s*sax", r"\ba\.\s?sax", r"\basax", r"アルトサックス", r"アルト"]),
    ("T.Sax", "TenorSaxophone", [r"tenor\s*sax", r"\bt\.\s?sax", r"\btsax", r"テナーサックス", r"テナー"]),
    ("B.Sax", "BaritoneSaxophone", [r"baritone\s*sax", r"bari\s*sax", r"\bb\.\s?sax", r"\bbsax", r"バリトンサックス", r"バリサク"]),
    ("Tp", "Trumpet", [r"trumpet", r"\btr?pt?\b", r"^tp(?=[\s.\d]|$)", r"tp(?=\s?\d)", r"トランペット", r"ペット"]),
    ("Cor", "Trumpet", [r"cornet", r"コルネット"]),
    ("Flgh", "Trumpet", [r"flugel", r"flügel", r"フリューゲル"]),
    ("Hr", "Horn", [r"horn", r"\bhn\b", r"\bhr\b", r"^hr(?=[\s.\d]|$)", r"hr(?=\s?\d)", r"ホルン"]),
    ("B.Tb", "BassTrombone", [r"bass\s*trombone", r"\bb\.\s?tb", r"バストロ"]),
    ("Tb", "Trombone", [r"trombone", r"\btr?b\b", r"^tb(?=[\s.\d]|$)", r"tb(?=\s?\d)", r"トロンボーン", r"ボーン"]),
    ("Euph", "Trombone", [r"euph", r"baritone", r"ユーフォ", r"バリトン"]),
    ("Tuba", "Tuba", [r"tuba", r"チューバ", r"テューバ"]),
    ("St.B", "Contrabass", [r"string\s*bass", r"contrabass", r"double\s*bass", r"\bst\.?\s?b\b", r"\bcb\b",
                            r"コントラバス", r"弦バス", r"ストリングベース"]),
    ("E.B", "ElectricBass", [r"electric\s*bass", r"\be\.\s?b(ass)?\b", r"エレキベース", r"エレベ"]),
    ("Pf", "Piano", [r"piano", r"\bpf\b", r"ピアノ"]),
    ("Hp", "Harp", [r"harp", r"ハープ"]),
    ("Timp", "Timpani", [r"timp", r"ティンパニ"]),
    ("Glock", "Glockenspiel", [r"glock", r"グロッケン", r"鉄琴"]),
    ("Xylo", "Xylophone", [r"xylo", r"シロフォン", r"木琴"]),
    ("Vib", "Vibraphone", [r"vib", r"ビブラフォン", r"ヴィブラフォン"]),
    ("Mar", "Marimba", [r"marimba", r"マリンバ"]),
    ("Mallet", None, [r"mallet", r"鍵盤"]),
    ("S.D.", None, [r"snare", r"\bs\.\s?d\b", r"スネア", r"小太鼓"]),
    ("B.D.", None, [r"bass\s*drum", r"\bb\.\s?d\b", r"バスドラ", r"大太鼓"]),
    ("Cym", None, [r"cymbal", r"\bcym", r"シンバル"]),
    ("Drs", None, [r"drum", r"\bdrs\b", r"ドラム"]),
    ("Perc", None, [r"perc", r"パーカッション", r"打楽器"]),
]

# 先頭の整理番号（"1." "03_" "12-" など）。"1st" のような序数は残す
_LEADING_INDEX = re.compile(r"^\d{1,3}\s*[._\-\s]\s*")
# 調性表記（"in Bb" "B♭" など）。パート番号の数字と紛れないよう番号抽出の前に除く
_KEY_MARK = re.compile(r"\bin\s+[a-g][b♭#♯]?\b|\b[a-g][b♭]\b|[a-g]♭")
_ORDINAL = re.compile(r"(\d)\s*(?:st|nd|rd|th)\b")
_TRAILING_NUMS = re.compile(r"(\d{1,2}(?:\s*[&,・/+]\s*\d{1,2})*)\s*\.?\s*$")
_ROMAN = re.compile(r"\b(iv|i{1,3})\s*$")
_ROMAN_VALUES = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}


@dataclass
class PartName:
    short: str             # 正規化後の略称（"Cl" など）。判定できなければ元のファイル名
    number: str            # パート番号（"1" "1&2" など）。無ければ ""
    order: int             # 総譜での並び順。判定できなければ末尾
    m21_class: Optional[str]
    recognized: bool

    @property
    def display(self) -> str:
        return f"{self.short} {self.number}".strip()

    @property
    def is_full_score(self) -> bool:
        return self.short == "Score"


def normalize_text(stem: str) -> str:
    text = unicodedata.normalize("NFKC", stem).lower()
    text = text.replace("_", " ").strip()
    return _LEADING_INDEX.sub("", text)


def _part_number(text: str) -> str:
    text = _KEY_MARK.sub(" ", text).strip(" .-")
    m = _ORDINAL.search(text)
    if m:
        return m.group(1)
    m = _TRAILING_NUMS.search(text)
    if m:
        return re.sub(r"\s*[&,・/+]\s*", "&", m.group(1))
    m = _ROMAN.search(text)
    if m:
        return _ROMAN_VALUES[m.group(1)]
    return ""


def identify(stem: str) -> PartName:
    """ファイル名（拡張子なし）からパート名を判定する。"""
    text = normalize_text(stem)
    for order, (short, m21_class, patterns) in enumerate(INSTRUMENTS):
        if any(re.search(p, text) for p in patterns):
            number = "" if short == "Score" else _part_number(text)
            return PartName(short, number, order, m21_class, True)
    return PartName(stem.strip(), "", len(INSTRUMENTS), None, False)


def make_instrument(part_name: PartName) -> instrument.Instrument:
    """music21 の楽器オブジェクトを作る。"Clarinet:m3" のように ':' の後ろで移調を上書きできる。"""
    inst = None
    if part_name.m21_class:
        cls_name, _, transposition = part_name.m21_class.partition(":")
        inst = getattr(instrument, cls_name)()
        if transposition:
            inst.transposition = interval.Interval(transposition)
    else:
        inst = instrument.Instrument()
    inst.partName = part_name.display
    inst.partAbbreviation = part_name.display
    if not part_name.m21_class:
        inst.instrumentName = part_name.display
    return inst
