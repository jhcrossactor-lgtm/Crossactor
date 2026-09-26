"""scan2muse — スキャンした楽譜（PDF/PNG/JPG）を oemer で読み取り、MuseScore の .mscz にする。

使い方: py scan2muse.py <入力フォルダ> [オプション]   （詳細は README.md / --help）

処理の流れ:
  1. フォルダ内の PDF / 画像を集める（1ファイル＝1パート。連番画像は1パートにまとめる）
  2. PDF は PyMuPDF で 300dpi の PNG に変換
  3. 各ページを oemer で MusicXML 化（ページごとに別プロセス。失敗ページはスキップして記録）
  4. music21 でページを結合し、ファイル名から判定したパート名・楽器を設定
  5. MuseScore CLI で .mscz に変換（パート譜ごと＋全パートの総譜）
"""
import argparse
import copy
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import List, Optional

TOOL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = TOOL_DIR / "config.json"
RUNNER = TOOL_DIR / "oemer_runner.py"

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
# 連番画像を1パートにまとめる時のページ番号表記（"Cl1_p1.png" "Tp 1 page2.jpg" "Hr-ページ3.png"）
# "Clarinet 1.png" のようなパート番号と区別するため、p/page/ページ の明示がある時だけまとめる
PAGE_SUFFIX = re.compile(r"[\s_\-]*(?:p|pg|page|ページ)[\s_\-]*(\d{1,3})$", re.IGNORECASE)

# onnxruntime 1.28 以降は oemer の unet_big モデル読込時に
# "ConvTranspose ... pads must not contain negative values" で失敗する（2026-09 確認）
ORT_MAX_EXCLUSIVE = (1, 28)

MUSESCORE_CANDIDATES = [
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
    r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\MuseScore 4\bin\MuseScore4.exe"),
    r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
]
MUSESCORE_NAMES = ["MuseScore4", "MuseScore4.exe", "mscore4", "musescore4", "MuseScore3", "mscore3", "mscore", "musescore"]

log = logging.getLogger("scan2muse")


@dataclass
class Source:
    """1パート分の入力（PDF 1つ、または連番画像の束）。"""
    stem: str
    files: List[Path]
    pages: List[Path] = field(default_factory=list)       # 変換後のページ画像
    xmls: List[Path] = field(default_factory=list)        # 読み取りに成功したページの MusicXML
    failed: List[str] = field(default_factory=list)       # 失敗したページの説明


# ---------------------------------------------------------------- 設定・事前チェック

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def find_musescore(config: dict) -> Optional[str]:
    """MuseScore の実行ファイルを探し、見つかったら config.json に記録する。"""
    saved = config.get("musescore_path")
    if saved and Path(saved).exists():
        return saved
    found = next((c for c in MUSESCORE_CANDIDATES if Path(c).exists()), None)
    if not found:
        found = next((shutil.which(n) for n in MUSESCORE_NAMES if shutil.which(n)), None)
    if not found and sys.platform == "win32":
        # 標準以外の場所にインストールされている場合に備えて Program Files 以下を探す
        for root in filter(None, {os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")}):
            hits = sorted(Path(root).glob("MuseScore*/bin/MuseScore*.exe"), reverse=True)
            if hits:
                found = str(hits[0])
                break
    if found:
        config["musescore_path"] = found
        save_config(config)
    return found


def check_onnxruntime() -> Optional[str]:
    """oemer が動く onnxruntime かを確認する。問題があればエラーメッセージを返す。"""
    versions = {}
    for dist in ("onnxruntime", "onnxruntime-gpu", "onnxruntime-directml"):
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            pass
    if not versions:
        return "onnxruntime が入っていません。setup.bat を実行してください。"
    for dist, ver in versions.items():
        nums = tuple(int(x) for x in re.findall(r"\d+", ver)[:2])
        if nums >= ORT_MAX_EXCLUSIVE:
            return (f"{dist} {ver} は oemer のモデルを読めません（1.28 以降の既知の非互換）。\n"
                    f"  対処: py -m pip install \"{dist}<1.28\"  （または setup.bat を実行）")
    return None


# ---------------------------------------------------------------- 入力の収集・画像化

def collect_sources(folder: Path) -> List[Source]:
    sources: List[Source] = []
    image_groups = {}
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        ext = path.suffix.lower()
        if not path.is_file() or path.name.startswith("~$"):
            continue
        if ext in PDF_EXTS:
            sources.append(Source(path.stem, [path]))
        elif ext in IMAGE_EXTS:
            m = PAGE_SUFFIX.search(path.stem)
            key = path.stem[:m.start()] if m else path.stem
            page_no = int(m.group(1)) if m else 0
            image_groups.setdefault(key, []).append((page_no, path))
    for key, items in image_groups.items():
        sources.append(Source(key, [p for _, p in sorted(items, key=lambda t: (t[0], t[1].name))]))
    return sorted(sources, key=lambda s: s.stem)


def render_pages(src: Source, page_dir: Path, dpi: int, limit_pages: Optional[int]) -> None:
    """入力を 1ページ=1PNG に揃えて page_dir に置く（PDF は dpi 指定でラスタライズ）。"""
    import pymupdf
    from PIL import Image, ImageOps

    page_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for file in src.files:
        if file.suffix.lower() in PDF_EXTS:
            with pymupdf.open(file) as doc:
                for page in doc:
                    if limit_pages and n >= limit_pages:
                        return
                    n += 1
                    out = page_dir / f"p{n:03d}.png"
                    if not out.exists():
                        page.get_pixmap(dpi=dpi, alpha=False).save(out)
                    src.pages.append(out)
        else:
            if limit_pages and n >= limit_pages:
                return
            n += 1
            out = page_dir / f"p{n:03d}.png"
            if not out.exists():
                # スマホ写真の向き（EXIF）を反映し、RGB の PNG に統一して oemer に渡す
                with Image.open(file) as im:
                    ImageOps.exif_transpose(im).convert("RGB").save(out)
            src.pages.append(out)


# ---------------------------------------------------------------- oemer

def run_oemer(page: Path, out_dir: Path, timeout: int, deskew: bool, force: bool) -> Path:
    """1ページを oemer にかける。成功したら MusicXML のパスを返し、失敗したら例外を投げる。"""
    xml = out_dir / f"{page.stem}.musicxml"
    if xml.exists() and not force:
        log.info("    %s: 読み取り済み（再利用）", page.name)
        return xml
    cmd = [sys.executable, str(RUNNER), str(page), str(out_dir)]
    if not deskew:
        cmd.append("--without-deskew")
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"タイムアウト（{timeout}秒）")
    if proc.returncode != 0 or not xml.exists():
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-6:])
        raise RuntimeError(f"oemer 終了コード {proc.returncode}\n{tail}")
    log.info("    %s: OK（%.0f秒）", page.name, time.time() - started)
    return xml


# ---------------------------------------------------------------- music21 後処理

def join_pages(xmls: List[Path]):
    """ページごとの MusicXML を時間方向に連結し、music21 の Part のリストを返す（五線ごとに1つ）。"""
    from music21 import converter, stream

    joined: List = []
    for page_idx, xml in enumerate(xmls):
        score = converter.parse(str(xml))
        parts = list(score.parts)
        if page_idx and len(parts) != len(joined):
            log.warning("    %s: 段数が前のページと違います（%d → %d）。先頭から順に連結します",
                        xml.name, len(joined), len(parts))
        for i, part in enumerate(parts):
            if i >= len(joined):
                joined.append(stream.Part())
            target = joined[i]
            for m in part.getElementsByClass(stream.Measure):
                m = copy.deepcopy(m)
                m.number = len(target.getElementsByClass(stream.Measure)) + 1
                target.append(m)
    return joined


def build_part_streams(src: Source, part_name):
    """連結済みの Part に楽器名を付ける。移調楽器は記譜音のまま <transpose> を付ける。"""
    from instruments import make_instrument
    from music21 import instrument

    parts = join_pages(src.xmls)
    for i, part in enumerate(parts):
        for old in list(part.recurse().getElementsByClass(instrument.Instrument)):
            old.activeSite.remove(old)
        inst = make_instrument(part_name)
        if len(parts) > 1:
            inst.partName = f"{part_name.display} ({i + 1})"
            inst.partAbbreviation = inst.partName
        part.insert(0, inst)
        part.partName = inst.partName
        part.partAbbreviation = inst.partAbbreviation
        part.atSoundingPitch = False  # oemer が読むのは記譜音
    return parts


def write_score(parts, title: str, xml_path: Path) -> None:
    from music21 import metadata as m21meta
    from music21 import stream

    score = stream.Score()
    score.metadata = m21meta.Metadata()
    score.metadata.title = title
    score.metadata.composer = ""
    for p in parts:
        score.insert(0, p)
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(xml_path))


# ---------------------------------------------------------------- MuseScore

def to_mscz(musescore: str, xml_path: Path, mscz_path: Path, timeout: int = 300) -> None:
    mscz_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if sys.platform != "win32":
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    proc = subprocess.run([musescore, "-o", str(mscz_path), str(xml_path)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    if proc.returncode != 0 or not mscz_path.exists():
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-6:])
        raise RuntimeError(f"MuseScore 終了コード {proc.returncode}\n{tail}")


# ---------------------------------------------------------------- メイン

def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "part"


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="スキャン楽譜 → oemer → MuseScore (.mscz) 一括変換")
    ap.add_argument("folder", help="PDF / PNG / JPG が入ったフォルダ")
    ap.add_argument("--out", default=str(TOOL_DIR / "output"), help="出力先（既定: scan2muse\\output）")
    ap.add_argument("--list", action="store_true", help="処理せず、入力ファイルと判定パート名の一覧だけ表示")
    ap.add_argument("--limit-files", type=int, help="先頭 N ファイルだけ処理（動作確認用）")
    ap.add_argument("--limit-pages", type=int, help="各ファイルの先頭 N ページだけ処理（動作確認用）")
    ap.add_argument("--dpi", type=int, default=300, help="PDF を画像にする解像度（既定 300）")
    ap.add_argument("--timeout", type=int, default=1800, help="1ページあたりの oemer 制限時間・秒（既定 1800）")
    ap.add_argument("--no-deskew", action="store_true", help="oemer の傾き補正を切る（まっすぐな電子PDF向け・高速）")
    ap.add_argument("--no-combine", action="store_true", help="全パートの総譜を作らない")
    ap.add_argument("--force", action="store_true", help="読み取り済みページも oemer をやり直す")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    sys.path.insert(0, str(TOOL_DIR))
    from instruments import identify

    args = parse_args(argv)
    folder = Path(args.folder.strip('"')).expanduser()
    if not folder.is_dir():
        print(f"[エラー] フォルダが見つかりません: {folder}")
        return 2

    sources = collect_sources(folder)
    if args.limit_files:
        sources = sources[:args.limit_files]
    if not sources:
        print(f"[エラー] PDF / PNG / JPG がありません: {folder}")
        return 2

    if args.list:
        print(f"入力フォルダ: {folder}")
        for src in sources:
            pn = identify(src.stem)
            mark = "" if pn.recognized else "   ← 楽器名を判定できず（ファイル名のまま使用）"
            print(f"  {pn.display:12s} ← {', '.join(f.name for f in src.files)}{mark}")
        return 0

    job_dir = Path(args.out) / safe_filename(folder.name)
    setup_logging(job_dir / "scan2muse.log")
    log.info("==== scan2muse 開始: %s", folder)

    problem = check_onnxruntime()
    if problem:
        log.error(problem)
        return 2
    musescore = find_musescore(load_config())
    if not musescore:
        log.error("MuseScore が見つかりません。config.json の musescore_path に MuseScore4.exe のパスを書いてください。")
        return 2
    log.info("MuseScore: %s", musescore)

    finished = []  # (PartName, [music21 Part])
    for idx, src in enumerate(sources, 1):
        pn = identify(src.stem)
        log.info("[%d/%d] %s → パート名「%s」%s", idx, len(sources), src.stem, pn.display,
                 "" if pn.recognized else "（楽器名を判定できず）")
        work = job_dir / "work" / safe_filename(src.stem)
        try:
            render_pages(src, work / "pages", args.dpi, args.limit_pages)
        except Exception as e:  # 壊れたPDF・画像など。このファイルだけ飛ばす
            src.failed.append(f"画像化に失敗: {e}")
            log.error("    画像化に失敗しました: %s", e)
            continue
        for page in src.pages:
            try:
                src.xmls.append(run_oemer(page, work / "xml", args.timeout, not args.no_deskew, args.force))
            except Exception as e:
                src.failed.append(f"{page.name}: {e}")
                log.error("    %s: 失敗 — %s", page.name, e)
        if not src.xmls:
            log.error("    読み取れたページが無いため、このパートは出力しません")
            continue
        try:
            parts = build_part_streams(src, pn)
            name = safe_filename(f"{pn.order:02d}_{pn.display}" if pn.recognized else pn.display)
            xml_path = work / f"{name}.musicxml"
            write_score(parts, f"{folder.name} - {pn.display}", xml_path)
            to_mscz(musescore, xml_path, job_dir / "parts" / f"{name}.mscz")
            log.info("    → parts/%s.mscz（%d/%d ページ）", name, len(src.xmls), len(src.pages))
            finished.append((pn, parts))
        except Exception as e:
            src.failed.append(f"パート出力に失敗: {e}")
            log.error("    パート出力に失敗しました: %s", e)

    # 全パートをまとめた総譜（フルスコアのスキャンは重複するので除外）
    combine = [(pn, parts) for pn, parts in finished if not pn.is_full_score]
    if not args.no_combine and len(combine) > 1:
        combine.sort(key=lambda t: (t[0].order, t[0].number))
        all_parts = [copy.deepcopy(p) for _, parts in combine for p in parts]
        measures = {pn.display: len(parts[0].getElementsByClass("Measure")) for pn, parts in combine}
        if len(set(measures.values())) > 1:
            log.warning("パートごとの小節数が揃っていません（読み取り誤差）: %s", measures)
        try:
            xml_path = job_dir / "work" / "_all.musicxml"
            write_score(all_parts, folder.name, xml_path)
            to_mscz(musescore, xml_path, job_dir / f"{safe_filename(folder.name)}_総譜.mscz")
            log.info("総譜 → %s_総譜.mscz（%d パート）", safe_filename(folder.name), len(all_parts))
        except Exception as e:
            log.error("総譜の出力に失敗しました: %s", e)

    failures = [(s.stem, f) for s in sources for f in s.failed]
    log.info("==== 完了: パート %d/%d 出力、失敗 %d 件", len(finished), len(sources), len(failures))
    for stem, msg in failures:
        log.info("  [失敗] %s / %s", stem, msg.splitlines()[0])
    log.info("出力先: %s", job_dir)
    return 0 if finished else 1


if __name__ == "__main__":
    sys.exit(main())
