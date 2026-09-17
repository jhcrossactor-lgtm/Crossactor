#!/usr/bin/env python3
"""ヴィラPV生成パイプライン CLI。

  python run.py --stage 1                 # 人物合成（生成順に沿って1カットずつ確認）
  python run.py --stage 1 --resume        # 合格済みは飛ばして続きから
  python run.py --cut 04 --stage 1        # カット単位で作り直し
  python run.py --cut 05,04,07,09 --stage 1   # 複数カットを指定順に
  python run.py --stage 2                 # 動画化（stage1の合格が前提）
  python run.py --stage 3                 # 結合して output/ に書き出し
  python run.py --stage all               # 1 -> 目視確認で停止
  python run.py approve 03 05             # 画像を見てから合格にする（--yes で回したあと）
  python run.py reject 04                 # 不合格にする（参照チェーンから外れる）
  python run.py status                    # 各工程の進み具合
  python run.py check                     # 素材と環境の事前チェック
  python run.py connect                   # 画像API・動画APIの疎通確認
  python run.py publish --deliver-to G:\\pv   # 成果物を外付けSSD等へコピー
  python run.py connect --smoke           # 実際に1枚編集して確かめる（課金あり）

別物件で使うときは projects/<物件名>/ を作って cuts.yaml と input/ を差し替える。
  python run.py --project projects/別物件 --stage 1

作業一式を別ドライブに置くときは、環境変数 PVP_PROJECT にそのパスを入れておけば
毎回 --project を書かなくてよい。
  $env:PVP_PROJECT = 'G:\\pv\\villa_test'      # PowerShell、そのセッションだけ
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pvp.connect import run_connect  # noqa: E402
from pvp.delivery import deliver, deliver_if_auto, delivery_dir  # noqa: E402
from pvp.cuts import cut_by_id, load_cuts, stage1_order  # noqa: E402
from pvp.stages.stage1 import run_stage1, stage1_status  # noqa: E402
from pvp.stages.stage2 import run_stage2  # noqa: E402
from pvp.stages.stage3 import run_stage3  # noqa: E402
from pvp.util import RunLogger, load_dotenv, load_project  # noqa: E402

DEFAULT_PROJECT = "projects/villa_test"


def default_project() -> str:
    """既定の物件ディレクトリ。環境変数 PVP_PROJECT で上書きできる。

    作業一式を別ドライブ（外付けSSD等）に置いたとき、毎回 --project を
    打たなくて済むようにするため。
    """
    import os

    return os.environ.get("PVP_PROJECT", "").strip() or DEFAULT_PROJECT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ヴィラPV生成パイプライン",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "status", "check", "connect", "publish",
                                 "approve", "reject"],
                        help="実行する内容")
    parser.add_argument("cut_ids", nargs="*",
                        help="approve / reject の対象カット（例: approve 03 05）")
    parser.add_argument("--project", default=None,
                        help="物件ディレクトリ。省略時は環境変数 PVP_PROJECT、"
                             "それも無ければ projects/villa_test")
    parser.add_argument("--stage", default="1", help="1 / 2 / 3 / all")
    parser.add_argument("--cut", default=None,
                        help="カット番号。カンマ区切りで複数可（例: 04 / 05,04,07,09）。省略で全カット")
    parser.add_argument("--provider", default=None, help="image/video 両方を上書き（mock など）")
    parser.add_argument("--image-provider", default=None, help="画像プロバイダを上書き")
    parser.add_argument("--video-provider", default=None, help="動画プロバイダを上書き")
    parser.add_argument("--yes", action="store_true", help="目視確認を省いて自動合格にする")
    parser.add_argument("--resume", action="store_true",
                        help="stage1 で、合格済みのカットを作り直さずに飛ばす")
    parser.add_argument("--no-chain", action="store_true",
                        help="合格カットを人物参照に足さない（設定シートのみ使う）")
    parser.add_argument("--force", action="store_true",
                        help="stage1 の合格チェックを飛ばして stage2 に進む")
    parser.add_argument("--music", default=None, help="BGM音源のパス（stage3）")
    parser.add_argument("--smoke", action="store_true",
                        help="connect で実際に1枚編集して確かめる（課金が発生する）")
    parser.add_argument("--deliver-to", default=None,
                        help="成果物のコピー先（外付けSSDやGoogle Driveの同期フォルダ）。"
                             "config.yaml の delivery.dir より優先する")
    parser.add_argument("--no-video", action="store_true",
                        help="connect で動画APIのチェックを省く")
    return parser


def cmd_check(project) -> int:
    from pvp.util import ffmpeg_bin, ffprobe_bin

    print(f"プロジェクト: {project.root}")
    problems = 0
    try:
        print(f"  ffmpeg : {ffmpeg_bin()}")
    except SystemExit as exc:
        print(f"  [NG] {exc}")
        problems += 1
    probe = ffprobe_bin()
    print(f"  ffprobe: {probe or '(無し — ffmpegで代替する)'}")

    sheet = (project.cuts.get("character_sheet") or "").strip()
    if sheet:
        found = (project.input_dir / sheet).exists() or bool(
            list(project.input_dir.glob(f"{Path(sheet).stem}.*"))
        )
        print(f"  人物設定シート {sheet}: {'OK' if found else 'NG (input/ に無い)'}")
        problems += 0 if found else 1

    from pvp.imageprep import describe_image

    for cut in load_cuts(project):
        try:
            path = cut.source_path()
            if path.suffix.lower() in {".mov", ".mp4"}:
                print(f"  cut{cut.id} 素材 {path.name}: OK (動画)")
            else:
                desc = describe_image(path)
                print(f"  cut{cut.id} 素材 {path.name}: {desc}")
                if desc.startswith("NG"):
                    problems += 1
        except Exception as exc:
            print(f"  cut{cut.id} 素材: NG — {exc}")
            problems += 1

    import os

    for section, env in (("image", (project.config.get("image") or {}).get("api_key_env")),
                         ("video/gemini", ((project.config.get("video") or {}).get("gemini") or {}).get("api_key_env")),
                         ("video/minimax", ((project.config.get("video") or {}).get("minimax") or {}).get("api_key_env"))):
        if env:
            print(f"  {section} APIキー {env}: {'設定済み' if os.environ.get(env) else '未設定'}")

    total = sum(c.duration for c in load_cuts(project))
    xfade = float((project.config.get("assemble") or {}).get("xfade_duration", 0.5))
    n = len(load_cuts(project))
    finished = total - xfade * max(0, n - 1)
    print(f"  カット合計 {total:.1f}秒 / クロスディゾルブ{xfade}秒×{max(0, n-1)} "
          f"→ 完成尺 約{finished:.1f}秒")
    print("チェック完了" if problems == 0 else f"問題 {problems} 件")
    return 0 if problems == 0 else 1


def cmd_status(project) -> int:
    ok, ng = stage1_status(project)
    print(f"プロジェクト: {project.root}")
    print(f"  stage1 生成順: {' -> '.join(stage1_order(project))}")
    print(f"  stage1 合格  : {', '.join(ok) if ok else '(なし)'}")
    print(f"  stage1 未合格: {', '.join(ng) if ng else '(なし)'}")
    done2 = [c.id for c in load_cuts(project) if c.stage2_path().exists()]
    print(f"  stage2 完了  : {', '.join(done2) if done2 else '(なし)'}")
    outputs = sorted(p.name for p in project.output_dir.glob("*.mp4"))
    print(f"  output       : {', '.join(outputs) if outputs else '(なし)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project or default_project())
    if not project_root.is_absolute():
        project_root = HERE / project_root
    load_dotenv([project_root / ".env", HERE / ".env", HERE.parent / ".env"])
    project = load_project(project_root)

    if args.command == "check":
        return cmd_check(project)
    if args.command == "status":
        return cmd_status(project)
    if args.command in ("approve", "reject"):
        # 非対話で回したあと、画像を見てから合否を付け直すためのもの
        ids = [c.zfill(2) for c in args.cut_ids] or (
            [c.strip().zfill(2) for c in args.cut.split(",")] if args.cut else [])
        if not ids:
            raise SystemExit("対象カットを指定すること（例: python run.py approve 03 05）")
        for cid in ids:
            cut = cut_by_id(project, cid)
            approved = args.command == "approve"
            if approved and not cut.stage1_path().exists():
                raise SystemExit(f"cut{cid} の stage1 画像が無いので合格にできない")
            project.save_approval(cid, approved, "手動で" + ("合格" if approved else "不合格"))
            print(f"cut{cid}: {'合格' if approved else '不合格'} に設定した")
        return 0
    if args.command == "publish":
        logger = RunLogger(project.log_dir, "publish")
        dest = delivery_dir(project, args.deliver_to)
        if dest is None:
            raise SystemExit(
                "config.yaml の delivery.dir が空。コピー先（Google Drive の同期フォルダ）を書くこと"
            )
        copied = deliver(project, logger, override=args.deliver_to)
        print(f"\n{copied} 件をコピーした -> {dest / (project.cuts.get('project_name') or project.root.name)}")
        return 0
    if args.command == "connect":
        logger = RunLogger(project.log_dir, "connect")
        return run_connect(project, logger, smoke=args.smoke, video=not args.no_video)

    image_provider = args.image_provider or args.provider
    video_provider = args.video_provider or args.provider
    stages = ["1", "2", "3"] if args.stage == "all" else [args.stage]
    if args.stage not in {"1", "2", "3", "all"}:
        raise SystemExit("--stage は 1 / 2 / 3 / all のいずれか")

    logger = RunLogger(project.log_dir, f"stage{args.stage}")
    logger.log(f"開始 project={project.root.name} stage={args.stage} cut={args.cut or 'all'}")

    for stage in stages:
        if stage == "1":
            run_stage1(
                project, logger,
                only_cut=args.cut,
                provider_override=image_provider,
                interactive=not args.yes,
                chain_references=not args.no_chain,
                resume=args.resume,
            )
            ok, ng = stage1_status(project)
            logger.log(f"stage1 完了 合格={ok} 未合格={ng}")
            deliver_if_auto(project, logger, ["stage1", "logs"], args.deliver_to)
            if args.stage == "all":
                print()
                print("=" * 62)
                print(" 工程3: ここで停止する。stage1/ の画像を目視確認すること。")
                if ng:
                    print(f" 未合格のカット: {', '.join(ng)}")
                    print(" 作り直し例: python run.py --cut 04 --stage 1")
                print(" 問題なければ: python run.py --stage 2")
                print("=" * 62)
                return 0

        elif stage == "2":
            ok, ng = stage1_status(project)
            if ng and not args.force:
                raise SystemExit(
                    f"stage1 が未合格のカットがある: {', '.join(ng)}\n"
                    "作り直すか、確認済みなら --force を付けること。"
                )
            run_stage2(project, logger, only_cut=args.cut, provider_override=video_provider)
            logger.log("stage2 完了")
            deliver_if_auto(project, logger, ["stage2", "logs"], args.deliver_to)

        elif stage == "3":
            music = Path(args.music) if args.music else None
            out = run_stage3(project, logger, music_override=music)
            print(f"\n書き出し: {out}")
            deliver_if_auto(project, logger, ["output", "logs"], args.deliver_to)
            dest = delivery_dir(project, args.deliver_to)
            if dest is not None:
                print(f"コピー先: {dest / (project.cuts.get('project_name') or project.root.name)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
