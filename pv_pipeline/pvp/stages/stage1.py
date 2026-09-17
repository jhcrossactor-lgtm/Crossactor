"""工程2: 人物合成（画像編集API）。合格した画像を次のカットの人物参照に足していく。"""

from __future__ import annotations

from pathlib import Path

from ..cuts import Cut, cut_by_id, load_cuts, stage1_order
from ..providers.factory import build_image_provider
from ..util import Project, RunLogger


def _character_sheet(project: Project) -> Path | None:
    name = (project.cuts.get("character_sheet") or "").strip()
    if not name:
        return None
    path = project.input_dir / name
    if not path.exists():
        matches = sorted(project.input_dir.glob(f"{Path(name).stem}.*"))
        if matches:
            return matches[0]
        raise FileNotFoundError(f"人物設定シート {name} が {project.input_dir} に無い")
    return path


def _reference_chain(project: Project, cut: Cut, max_refs: int) -> list[Path]:
    """人物参照＝設定シート＋「合格済み」の先行カット画像。"""
    refs: list[Path] = []
    sheet = _character_sheet(project)
    if sheet:
        refs.append(sheet)

    approvals = project.load_approvals()
    for prior_id in stage1_order(project):
        if prior_id == cut.id:
            break
        record = approvals.get(prior_id)
        if not record or not record.get("approved"):
            continue
        prior = cut_by_id(project, prior_id)
        if prior.stage1_path().exists():
            refs.append(prior.stage1_path())
    # 編集対象の1枚ぶんを空けて上限に収める（新しい合格カットを優先して残す）
    limit = max(1, max_refs - 1)
    if len(refs) > limit:
        refs = refs[:1] + refs[-(limit - 1):]
    return refs


def run_stage1(
    project: Project,
    logger: RunLogger,
    only_cut: str | None = None,
    provider_override: str | None = None,
    interactive: bool = True,
    chain_references: bool = True,
    resume: bool = False,
) -> list[Path]:
    config = project.config
    provider = build_image_provider(config, provider_override)
    max_refs = int((config.get("image") or {}).get("max_reference_images", 16))

    # stage1_order は「人物参照を連鎖させるカット」の順序。
    # 人物なしの編集カット（01/10 など）は連鎖に関係ないので、そのあとに回す。
    order = stage1_order(project)
    order += sorted(
        c.id for c in load_cuts(project) if c.image_mode == "edit" and c.id not in order
    )
    if only_cut:
        targets = [t.strip().zfill(2) for t in str(only_cut).split(",") if t.strip()]
        for target in targets:
            cut = cut_by_id(project, target)   # 存在しない番号はここで止まる
            if cut.image_mode != "edit":
                logger.log(f"cut{target} は画像編集スキップ指定のため何もしない", cut=target)
        order = [t for t in targets if cut_by_id(project, t).image_mode == "edit"]

    approvals = project.load_approvals()
    produced: list[Path] = []
    for cut_id in order:
        cut = cut_by_id(project, cut_id)
        if cut.image_mode != "edit":
            logger.log(f"cut{cut.id} は画像編集スキップ", cut=cut.id, stage="1")
            continue

        # --resume: 合格済みで画像も残っているカットは作り直さない
        record = approvals.get(cut.id) or {}
        if resume and record.get("approved") and cut.stage1_path().exists():
            logger.log(f"cut{cut.id} は合格済みなので飛ばす（--resume）",
                       cut=cut.id, stage="1", skipped=True)
            continue

        images = [cut.source_path()]
        if cut.use_person_reference:
            refs = _reference_chain(project, cut, max_refs) if chain_references else (
                [p for p in [_character_sheet(project)] if p]
            )
            images += refs

        prompt = cut.image_prompt(config)
        prompt_file = logger.save_prompt(
            cut.id, "stage1", prompt,
            {
                "cut": cut.id,
                "provider": provider.name,
                "edit_target": images[0].name,
                "references": [p.name for p in images[1:]],
            },
        )
        logger.log(f"cut{cut.id} プロンプト保存: {prompt_file.name}", cut=cut.id, stage="1")

        out = provider.edit(prompt, images, cut.stage1_path(), logger, cut.id)
        produced.append(out)

        if interactive:
            answer = input(f"  cut{cut.id} -> {out} は合格か？ [y/N/q] ").strip().lower()
            if answer == "q":
                project.save_approval(cut.id, False, "中断")
                logger.log("ユーザー操作で中断", cut=cut.id, stage="1")
                break
            approved = answer == "y"
            project.save_approval(cut.id, approved, "目視確認")
            logger.log(f"cut{cut.id} 目視確認: {'合格' if approved else '不合格'}",
                       cut=cut.id, stage="1", approved=approved)
        else:
            project.save_approval(cut.id, True, "非対話のため自動合格")
            logger.log(f"cut{cut.id} 非対話モードのため自動合格扱い", cut=cut.id, stage="1")

    return produced


def stage1_status(project: Project) -> tuple[list[str], list[str]]:
    """(合格したカット, まだ合格していないカット) を返す。"""
    approvals = project.load_approvals()
    ok, ng = [], []
    for cut in load_cuts(project):
        if cut.image_mode != "edit":
            continue
        record = approvals.get(cut.id)
        if record and record.get("approved") and cut.stage1_path().exists():
            ok.append(cut.id)
        else:
            ng.append(cut.id)
    return ok, ng
