"""cuts.yaml の読み取りと、素材・プロンプトの解決。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import media

# 元素材が HEIC のときの変換先を置くサブフォルダ
CONVERTED_DIRNAME = "_converted"


class Cut:
    def __init__(self, raw: dict[str, Any], project) -> None:
        self.raw = raw
        self.project = project
        self.id = str(raw["id"]).zfill(2)
        self.source: str | None = raw.get("source")
        self.duration: float = float(raw.get("duration", 4))
        self.image_mode: str = (raw.get("image") or {}).get("mode", "edit")
        self.image_instruction: str = (raw.get("image") or {}).get("instruction", "")
        self.use_person_reference: bool = bool((raw.get("image") or {}).get("person_reference", True))
        self.video_mode: str = (raw.get("video") or {}).get("mode", "ai")
        self.video_instruction: str = (raw.get("video") or {}).get("instruction", "")

    # -- パス ------------------------------------------------------------- #
    def source_path(self) -> Path:
        """input/ から素材を探す。HEIC しか無ければ JPEG に変換して返す。"""
        if not self.source:
            raise RuntimeError(f"cut{self.id}: source が未定義")
        direct = self.project.input_dir / self.source
        if direct.exists():
            return direct

        stem = Path(self.source).stem
        candidates = sorted(
            p for p in self.project.input_dir.glob(f"{stem}.*")
            if p.is_file() and not p.name.startswith(".")
        )
        for path in candidates:
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".mov", ".mp4"}:
                return path
        for path in candidates:
            if path.suffix.lower() in {".heic", ".heif"}:
                converted = self.project.input_dir / CONVERTED_DIRNAME / f"{stem}.jpg"
                if not converted.exists():
                    media.convert_heic(path, converted)
                return converted
        raise FileNotFoundError(
            f"cut{self.id}: 素材 {self.source} が {self.project.input_dir} に無い"
        )

    def stage1_path(self) -> Path:
        return self.project.stage1_dir / f"cut{self.id}.png"

    def stage2_path(self) -> Path:
        return self.project.stage2_dir / f"cut{self.id}.mp4"

    def stage2_raw_path(self) -> Path:
        return self.project.stage2_dir / "_raw" / f"cut{self.id}.mp4"

    # -- プロンプト -------------------------------------------------------- #
    def image_prompt(self, config: dict[str, Any]) -> str:
        prompts = config.get("prompts") or {}
        base = (prompts.get("image_common") or "").strip()
        if not self.use_person_reference:
            base = (prompts.get("image_common_no_person") or base).strip()
        attach = (prompts.get("image_attachment_note") or "").strip()
        wardrobe = (prompts.get("wardrobe") or "").strip()
        parts = [base]
        # 服装指定は人物が出るカットだけに差し込む
        if wardrobe and self.use_person_reference:
            parts.append(wardrobe)
        if attach and self.use_person_reference:
            parts.append(attach)
        if self.image_instruction:
            parts.append("このカットの指示：" + self.image_instruction.strip())
        return "\n\n".join(p for p in parts if p)

    def video_prompt(self, config: dict[str, Any]) -> str:
        prompts = config.get("prompts") or {}
        base = (prompts.get("video_common") or "").strip()
        parts = [base]
        if self.video_instruction:
            parts.append("このカットの動き：" + self.video_instruction.strip())
        return "\n\n".join(p for p in parts if p)


def load_cuts(project) -> list[Cut]:
    raw_cuts = project.cuts.get("cuts") or []
    return [Cut(raw, project) for raw in raw_cuts]


def cut_by_id(project, cut_id: str) -> Cut:
    target = str(cut_id).zfill(2)
    for cut in load_cuts(project):
        if cut.id == target:
            return cut
    raise SystemExit(f"cut{target} が cuts.yaml に無い")


def stage1_order(project) -> list[str]:
    """人物参照を連鎖させるための生成順。未指定なら定義順。"""
    order = project.cuts.get("stage1_order")
    if order:
        return [str(c).zfill(2) for c in order]
    return [c.id for c in load_cuts(project) if c.image_mode == "edit"]
