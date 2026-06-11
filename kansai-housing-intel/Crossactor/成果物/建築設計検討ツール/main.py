"""建築設計検討ツール エントリーポイント

2段階実行:
  Step 1 - 境界確認モード（境界番号を確認する）
    python main.py <PDF> --check-boundary

  Step 2 - 検討実行モード（番号で道路・隣地を指定して計算）
    python main.py <PDF> --road 0 2 --neighbor 1 3 4 [--road-width 6.0] [options]
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

from core.pdf_parser import parse_site_pdf
from core.site_model import SiteModel
from core.boundary_classifier import (
    extract_edges, print_edge_table, apply_boundary_types,
    road_edges, neighbor_edges,
)
from calculations.coverage_far import calculate_coverage_far
from calculations.setback_shadow import (
    calc_road_slope, calc_adjacent_slope, calc_shadow, calc_boundary_distance
)
from calculations.road_slope_envelope import build_road_slope_envelope
from output.dxf_generator import generate_dxf, generate_boundary_check_dxf
from output.pdf_generator import generate_pdf, generate_boundary_check_pdf


OUTPUT_DIR = Path("G:/マイドライブ/claude/成果物/建築設計検討ツール/output_files")


def step1_check_boundary(pdf_path: str, road_width: float | None) -> None:
    """境界確認モード: 辺番号付きDXFを出力してテーブルを表示する"""
    print(f"[1/2] PDFを解析中: {pdf_path}")
    data = parse_site_pdf(pdf_path)
    site = SiteModel.from_parsed(data, road_width_override=road_width)

    if site.polygon is None:
        print("[エラー] 敷地ポリゴンが取得できませんでした。")
        sys.exit(1)

    parcels = ", ".join(site.parcel_numbers) if site.parcel_numbers else "—"
    print(f"      地番: {parcels}  面積: {site.site_area_m2}m²")

    edges = extract_edges(site.polygon)
    print_edge_table(edges)

    # 番号付き図面を出力（DXF + PDF）
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dxf_path = OUTPUT_DIR / "境界確認図.dxf"
    pdf_path_out = OUTPUT_DIR / "境界確認図.pdf"
    generate_boundary_check_dxf(site.polygon, dxf_path)
    generate_boundary_check_pdf(site.polygon, pdf_path_out, edges)
    print(f"[2/2] 境界確認図を出力しました:")
    print(f"      DXF : {dxf_path}")
    print(f"      PDF : {pdf_path_out}  ← CADソフト不要でブラウザ・Acrobatで確認可")
    print()
    print("次のステップ: 上の番号を確認して以下のように実行してください")
    print(f'  python -X utf8 main.py "{pdf_path}" --road <番号> --neighbor <番号> [--road-width <幅員>]')
    print("  例: python -X utf8 main.py ... --road 0 --neighbor 1 2 3 --road-width 6.0")


def step2_run(
    pdf_path: str,
    road_indices: list[int],
    neighbor_indices: list[int],
    road_width: float | None,
    building_height: float,
    eave_height: float,
    floors: int,
) -> None:
    """検討実行モード: 境界種別を指定して計算・出力する"""
    print(f"[1/5] PDFを解析中: {pdf_path}")
    data = parse_site_pdf(pdf_path)
    site = SiteModel.from_parsed(data, road_width_override=road_width)

    parcels = ", ".join(site.parcel_numbers) if site.parcel_numbers else "—"
    print(f"      地番: {parcels}  用途地域: {site.zone_info.zone_name}  面積: {site.site_area_m2}m²")

    if site.polygon is None:
        print("[エラー] 敷地ポリゴンが取得できませんでした。")
        sys.exit(1)

    # 境界種別を設定
    edges = extract_edges(site.polygon)
    apply_boundary_types(edges, road_indices, neighbor_indices, road_width)

    print("      境界種別:")
    for e in edges:
        print(f"        辺{e.index}: {e.kind}  ({e.length_m:.2f}m)")

    print("[2/5] 建蔽率・容積率を計算中...")
    far_result = calculate_coverage_far(site)

    print("[3/5] 斜線・日影・境界距離を計算中...")
    road_slope   = calc_road_slope(site, building_height)
    adj_slope    = calc_adjacent_slope(site, building_height)
    shadow       = calc_shadow(site, building_height, eave_height, floors)
    boundary     = calc_boundary_distance(site)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("[4/5] DXFを出力中...")
    dxf_path = OUTPUT_DIR / f"検討図_{timestamp}.dxf"
    generate_dxf(site, far_result, road_slope, dxf_path, edges=edges)

    print("[5/5] 計算書PDFを出力中...")
    pdf_out = OUTPUT_DIR / f"法規検討計算書_{timestamp}.pdf"
    generate_pdf(site, far_result, road_slope, adj_slope, shadow, boundary, pdf_out)

    # 境界確認PDF（辺種別確定版）も同時出力
    boundary_pdf = OUTPUT_DIR / f"境界確認図_{timestamp}.pdf"
    generate_boundary_check_pdf(site.polygon, boundary_pdf, edges)

    print()
    print("=" * 52)
    print("完了")
    print(f"  計算書PDF    : {pdf_out}")
    print(f"  境界確認PDF  : {boundary_pdf}")
    print(f"  検討図DXF    : {dxf_path}")
    print()
    print("--- 検討結果サマリ ---")
    print(f"  建蔽率      : {far_result.max_coverage_ratio*100:.0f}%"
          f"  (最大建築面積: {far_result.max_building_area_m2:.1f}m²)")
    print(f"  容積率（有効）: {far_result.effective_far*100:.0f}%"
          f"  (最大延床面積: {far_result.effective_total_floor_area_m2:.1f}m²)")
    if road_slope and road_slope.road_width_m:
        print(f"  道路斜線    : 境界最大高さ {road_slope.max_height_at_boundary_m:.1f}m")
    if shadow.regulated:
        print(f"  日影規制    : 5mライン {shadow.limit_5m}h / 10mライン {shadow.limit_10m}h")
    else:
        print("  日影規制    : 対象外")
    print(f"  隣地境界距離  : {boundary['required_distance_m']}m 以上（民法234条）")


def main():
    parser = argparse.ArgumentParser(description="建築設計法規検討ツール")
    parser.add_argument("pdf", help="敷地PDFファイルのパス")
    parser.add_argument("--check-boundary", action="store_true",
                        help="境界確認モード: 辺番号を表示してDXFを出力する")
    parser.add_argument("--road",     type=int, nargs="+", default=[],
                        help="道路境界の辺番号（複数可）例: --road 0 2")
    parser.add_argument("--neighbor", type=int, nargs="+", default=[],
                        help="隣地境界の辺番号（複数可）例: --neighbor 1 3 4")
    parser.add_argument("--road-width",      type=float, default=None,
                        help="前面道路幅員(m) 手動指定")
    parser.add_argument("--building-height", type=float, default=10.0,
                        help="計画建物の高さ(m)")
    parser.add_argument("--eave-height",     type=float, default=7.5,
                        help="計画建物の軒高(m)")
    parser.add_argument("--floors",          type=int,   default=3,
                        help="階数")
    args = parser.parse_args()

    if args.check_boundary:
        step1_check_boundary(args.pdf, args.road_width)
    elif args.road or args.neighbor:
        step2_run(
            pdf_path=args.pdf,
            road_indices=args.road,
            neighbor_indices=args.neighbor,
            road_width=args.road_width,
            building_height=args.building_height,
            eave_height=args.eave_height,
            floors=args.floors,
        )
    else:
        print("モードを指定してください:")
        print("  境界確認: python -X utf8 main.py <PDF> --check-boundary")
        print("  検討実行: python -X utf8 main.py <PDF> --road 0 --neighbor 1 2 3")
        parser.print_help()


if __name__ == "__main__":
    main()
