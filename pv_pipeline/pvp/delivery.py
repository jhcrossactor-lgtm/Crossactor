"""成果物を Google Drive（デスクトップ版の同期フォルダ）などへコピーする。

作業ディレクトリごと Drive に置くと、stage2 の生成原本や一時ファイルまで
同期対象になって重くなる。ここでは「見せる物・渡す物」だけを選んでコピーする。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .util import Project, RunLogger

# 何をコピーするか。_raw（動画APIが返した原本）は大きいので既定では含めない。
KINDS = {
    "stage1": ("stage1", ("*.png", "*.jpg", "*.jpeg")),
    "stage2": ("stage2", ("*.mp4",)),
    "output": ("output", ("*.mp4",)),
    "logs": ("logs", ("*.log", "*.jsonl", "prompts/*.txt", "approvals.json")),
}


def delivery_dir(project: Project, override: str | None = None) -> Path | None:
    """コピー先を決める。--deliver-to > 環境変数 PVP_DELIVER_TO > config.yaml の順。"""
    import os

    raw = (override or os.environ.get("PVP_DELIVER_TO", "")
           or (project.config.get("delivery") or {}).get("dir") or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def deliver(
    project: Project,
    logger: RunLogger,
    kinds: list[str] | None = None,
    quiet: bool = False,
    override: str | None = None,
) -> int:
    """成果物をコピーする。コピーした件数を返す。"""
    conf = project.config.get("delivery") or {}
    dest_root = delivery_dir(project, override)
    if dest_root is None:
        return 0

    wanted = kinds or list(conf.get("include") or ["stage1", "stage2", "output", "logs"])
    project_name = project.cuts.get("project_name") or project.root.name

    if not dest_root.exists():
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.log(
                f"成果物のコピー先を作れない: {dest_root} ({exc})。"
                "Google Drive デスクトップ版が動いているか、パスが正しいか確認すること",
                delivery="failed",
            )
            return 0

    copied = 0
    skipped = 0
    for kind in wanted:
        if kind not in KINDS:
            logger.log(f"delivery.include の {kind!r} は不明なので無視する", delivery="unknown")
            continue
        subdir, patterns = KINDS[kind]
        src_dir = project.root / subdir
        if not src_dir.exists():
            continue
        for pattern in patterns:
            for src in sorted(src_dir.glob(pattern)):
                if not src.is_file():
                    continue
                dst = dest_root / project_name / subdir / src.relative_to(src_dir)
                # 中身が変わっていなければ触らない（Driveの再同期を起こさないため）
                if dst.exists() and dst.stat().st_size == src.stat().st_size \
                        and dst.stat().st_mtime >= src.stat().st_mtime:
                    skipped += 1
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src, dst)
                    copied += 1
                except OSError as exc:
                    logger.log(f"コピー失敗 {src.name}: {exc}", delivery="error")

    if copied or not quiet:
        logger.log(
            f"成果物をコピー: {copied}件（変更なし {skipped}件） -> "
            f"{dest_root / project_name}",
            delivery="ok", dest=str(dest_root / project_name), copied=copied,
        )
    return copied


def deliver_if_auto(project: Project, logger: RunLogger, kinds: list[str],
                    override: str | None = None) -> None:
    """各工程の終わりに呼ぶ。delivery.auto が false なら何もしない。"""
    conf = project.config.get("delivery") or {}
    if not conf.get("auto", True):
        return
    if delivery_dir(project, override) is None:
        return
    deliver(project, logger, kinds=kinds, quiet=True, override=override)
