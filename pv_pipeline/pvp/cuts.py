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
        self.indoor: bool = bool((raw.get("image") or {}).get("indoor", False))
        # 建物の構成をそろえるための追加参考画像。"stage1:03" / "input:xxx.jpg" / 相対パス
        self.extra_references: list[str] = list((raw.get("image") or {}).get("references") or [])
        self.reference_note: str = (raw.get("image") or {}).get("reference_note", "")
        self.video_mode: str = (raw.get("video") or {}).get("mode", "ai")
        self.video_instruction: str = (raw.get("video") or {}).get("instruction", "")
        # 仕上げで足すズーム。{to: 1.3, center: [x, y], start: 秒, end: 秒}（x,y は 0〜1）
        self.video_zoom: dict | None = (raw.get("video") or {}).get("zoom") or None
        # このカットだけ服装を上書きする（config の prompts.wardrobe の代わりに入る）
        self.wardrobe_override: str = (raw.get("image") or {}).get("wardrobe", "") or ""
        # 動画化の前に最初のコマを寄せて切り出す。{center: [x, y], size: 0.6}（size は元に対する幅の比）
        self.video_start_crop: dict | None = (raw.get("video") or {}).get("start_crop") or None
        # 仕上げで重ねる文字。[{text, font, size, x, y, start, fade, color, tracking, anchor}]
        self.video_overlays: list[dict] = list((raw.get("video") or {}).get("overlays") or [])

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

    def resolve_reference(self, spec: str) -> Path:
        """references の1項目をパスに解決する。"""
        spec = str(spec).strip()
        if spec.startswith("stage1:"):
            other = cut_by_id(self.project, spec.split(":", 1)[1])
            path = other.stage1_path()
            if not path.exists():
                raise FileNotFoundError(
                    f"cut{self.id}: 参考画像に指定した cut{other.id} の stage1 画像がまだ無い。先に作ること")
            return path
        if spec.startswith("input:"):
            return self.project.input_dir / spec.split(":", 1)[1]
        path = Path(spec)
        return path if path.is_absolute() else self.project.root / path

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
        wardrobe = (self.wardrobe_override or prompts.get("wardrobe") or "").strip()
        parts = [base]
        # 服装指定は人物が出るカットだけに差し込む
        if wardrobe and self.use_person_reference:
            parts.append(wardrobe)
        if attach and self.use_person_reference:
            parts.append(attach)
        indoor_note = (prompts.get("indoor_note") or "").strip()
        if indoor_note and self.indoor and self.use_person_reference:
            parts.append(indoor_note)
        if self.extra_references:
            n = len(self.extra_references)
            note = self.reference_note.strip() or "同じ建物を別の角度・時刻で撮った参考画像。建物の構成をそろえるために使う。"
            parts.append(f"添付の最後の{n}枚は建物の参考画像：{note} 構図・時刻・天候・人物は取り込まない。")
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
