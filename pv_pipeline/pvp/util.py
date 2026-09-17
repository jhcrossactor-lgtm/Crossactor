"""共通ユーティリティ（設定読み込み・ログ・パス解決）。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# --------------------------------------------------------------------------- #
# ログ
# --------------------------------------------------------------------------- #
class RunLogger:
    """人が読むログ (.log) と機械可読ログ (.jsonl) を同時に書く。

    プロンプトは全文を logs/prompts/ に保存する（工程の再現性のため）。
    """

    def __init__(self, log_dir: Path, name: str) -> None:
        self.log_dir = Path(log_dir)
        self.prompt_dir = self.log_dir / "prompts"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.text_path = self.log_dir / f"{stamp}_{name}.log"
        self.jsonl_path = self.log_dir / f"{stamp}_{name}.jsonl"

    def log(self, msg: str, **fields: Any) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        with self.text_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "msg": msg}
        record.update(fields)
        with self.jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def save_prompt(self, cut_id: str, stage: str, prompt: str, meta: dict[str, Any]) -> Path:
        """送信した全プロンプトを 1 ファイルに保存して、そのパスを返す。"""
        path = self.prompt_dir / f"cut{cut_id}_{stage}_{time.strftime('%Y%m%d-%H%M%S')}.txt"
        header = "\n".join(f"# {k}: {v}" for k, v in meta.items())
        path.write_text(f"{header}\n# ---- prompt ----\n{prompt}\n", encoding="utf-8")
        return path


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
@dataclass
class Project:
    """1 物件 = 1 ディレクトリ。cuts.yaml を差し替えれば別物件に流用できる。"""

    root: Path
    config: dict[str, Any] = field(default_factory=dict)
    cuts: dict[str, Any] = field(default_factory=dict)

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def stage1_dir(self) -> Path:
        return self.root / "stage1"

    @property
    def stage2_dir(self) -> Path:
        return self.root / "stage2"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def log_dir(self) -> Path:
        return self.root / "logs"

    @property
    def approvals_path(self) -> Path:
        return self.log_dir / "approvals.json"

    def ensure_dirs(self) -> None:
        for d in (self.input_dir, self.stage1_dir, self.stage2_dir, self.output_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- 合格カットの記録（人物参照の連鎖に使う） ---------------------------- #
    def load_approvals(self) -> dict[str, Any]:
        if self.approvals_path.exists():
            return json.loads(self.approvals_path.read_text(encoding="utf-8"))
        return {}

    def save_approval(self, cut_id: str, approved: bool, note: str = "") -> None:
        data = self.load_approvals()
        data[cut_id] = {"approved": approved, "note": note, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.approvals_path.parent.mkdir(parents=True, exist_ok=True)
        self.approvals_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(root: Path) -> Project:
    root = Path(root).resolve()
    config_path = root / "config.yaml"
    cuts_path = root / "cuts.yaml"
    if not config_path.exists():
        raise SystemExit(f"config.yaml が見つからない: {config_path}")
    if not cuts_path.exists():
        raise SystemExit(f"cuts.yaml が見つからない: {cuts_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
    cuts = yaml.safe_load(cuts_path.read_text(encoding="utf-8-sig")) or {}
    project = Project(root=root, config=config, cuts=cuts)
    project.ensure_dirs()
    return project


def load_dotenv(paths: list[Path]) -> None:
    """.env を読んで os.environ に載せる（既存の環境変数は上書きしない）。"""
    for path in paths:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def require_api_key(env_name: str) -> str:
    key = os.environ.get(env_name, "").strip()
    if not key:
        raise SystemExit(
            f"APIキー {env_name} が未設定。プロジェクト直下かリポジトリ直下の .env に "
            f"{env_name}=... を書くか、環境変数で渡すこと。"
        )
    return key


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #
def _resolve_binary(name: str) -> str:
    """PATH の ffmpeg/ffprobe を優先し、無ければ imageio-ffmpeg 同梱版を使う。"""
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # pragma: no cover - 環境依存
            pass
    return ""


FFMPEG = None
FFPROBE = None


def ffmpeg_bin() -> str:
    global FFMPEG
    if FFMPEG is None:
        FFMPEG = _resolve_binary("ffmpeg")
    if not FFMPEG:
        raise SystemExit(
            "ffmpeg が見つからない。インストールすること "
            "(macOS: brew install ffmpeg / Ubuntu: apt install ffmpeg)。"
        )
    return FFMPEG


def ffprobe_bin() -> str:
    """ffprobe は無くても動くようにしてある（無いときは ffmpeg で代替する）。"""
    global FFPROBE
    if FFPROBE is None:
        FFPROBE = _resolve_binary("ffprobe")
    return FFPROBE


def run_cmd(cmd: list[str], logger: RunLogger | None = None) -> subprocess.CompletedProcess:
    if logger:
        logger.log("exec: " + " ".join(cmd[:3]) + f" ... ({len(cmd)} args)", cmd=cmd)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"コマンド失敗 (exit {proc.returncode}):\n{' '.join(cmd)}\n{tail}")
    return proc


def _ffmpeg_probe_text(path: Path) -> str:
    """ffprobe が無い環境用。ffmpeg の解析出力をそのまま返す。"""
    proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True)
    return proc.stderr


def probe_duration(path: Path) -> float:
    probe = ffprobe_bin()
    if probe:
        proc = run_cmd([
            probe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ])
        text = proc.stdout.strip()
        if text and text != "N/A":
            return float(text)

    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", _ffmpeg_probe_text(path))
    if not match:
        raise RuntimeError(f"尺を取得できない: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def has_audio_stream(path: Path) -> bool:
    probe = ffprobe_bin()
    if probe:
        proc = run_cmd([
            probe, "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(path),
        ])
        return bool(proc.stdout.strip())
    return bool(re.search(r"Stream #\d+:\d+.*: Audio:", _ffmpeg_probe_text(path)))
