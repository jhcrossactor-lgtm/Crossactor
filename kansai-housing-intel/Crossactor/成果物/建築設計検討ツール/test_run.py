"""
計算・出力モジュールの動作確認テスト
PDF解析をスキップして、既知の敷地データを直接投入して全パイプラインを検証する
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from shapely.geometry import Polygon

from core.law_database import ZoneInfo
from core.site_model import SiteModel, Road
from calculations.coverage_far import calculate_coverage_far
from calculations.setback_shadow import (
    calc_road_slope, calc_adjacent_slope, calc_shadow, calc_boundary_distance
)
from output.dxf_generator import generate_dxf
from output.pdf_generator import generate_pdf

# ---- テスト用敷地データ（第一種中高層住居専用地域 / 200m²）----
# 敷地ポリゴン: 10m × 20m の矩形（原点基準）
polygon = Polygon([(0, 0), (10, 0), (10, 20), (0, 20)])

zone_info = ZoneInfo.from_zone_name(
    "第一種中高層住居専用地域",
    coverage_override=0.60,
    far_override=2.00,
)

site = SiteModel(
    address="東京都新宿区○○一丁目1番1号",
    zone_info=zone_info,
    site_area_m2=200.0,
    polygon=polygon,
    roads=[Road(width_m=6.0, direction="南")],
    fire_zone="準防火地域",
)

# ---- 計画建物の諸元 ----
BUILDING_HEIGHT = 12.0   # m
EAVE_HEIGHT     = 9.5    # m
FLOORS          = 4

print("=" * 55)
print("建築設計検討ツール テスト実行")
print("=" * 55)
print(f"所在地  : {site.address}")
print(f"用途地域: {site.zone_info.zone_name}")
print(f"敷地面積: {site.site_area_m2} m²")
print(f"防火地域: {site.fire_zone}")
print(f"計画高さ: {BUILDING_HEIGHT}m / 軒高: {EAVE_HEIGHT}m / {FLOORS}階")
print()

# ---- 計算 ----
far_result  = calculate_coverage_far(site)
road_slope  = calc_road_slope(site, BUILDING_HEIGHT)
adj_slope   = calc_adjacent_slope(site, BUILDING_HEIGHT)
shadow      = calc_shadow(site, BUILDING_HEIGHT, EAVE_HEIGHT, FLOORS)
boundary    = calc_boundary_distance(site)

print("【建蔽率・容積率】")
print(f"  建蔽率      : {far_result.max_coverage_ratio*100:.0f}%  → 最大建築面積 {far_result.max_building_area_m2:.1f} m²")
print(f"  容積率(有効): {far_result.effective_far*100:.0f}%  → 最大延床面積 {far_result.effective_total_floor_area_m2:.1f} m²")
for n in far_result.notes:
    print(f"  ※ {n}")

print()
print("【道路斜線】")
for n in road_slope.notes:
    print(f"  {n}")
print(f"  道路境界での最大高さ: {road_slope.max_height_at_boundary_m:.1f} m")

print()
print("【隣地斜線】")
for n in adj_slope.notes:
    print(f"  {n}")

print()
print("【日影規制】")
if shadow.regulated:
    print(f"  測定面高さ: {shadow.measurement_height_m} m")
    print(f"  5m ライン: {shadow.limit_5m}h / 10m ライン: {shadow.limit_10m}h")
for n in shadow.notes:
    print(f"  {n}")

print()
print("【隣地境界距離（民法234条）】")
print(f"  必要距離: {boundary['required_distance_m']} m 以上")

# ---- 出力 ----
out_dir = Path("G:/マイドライブ/claude/成果物/建築設計検討ツール/output_files")
out_dir.mkdir(parents=True, exist_ok=True)

print()
print("DXF 出力中...", end=" ")
dxf_path = out_dir / "test_検討図.dxf"
generate_dxf(site, far_result, road_slope, dxf_path)
print(f"OK → {dxf_path}")

print("PDF 出力中...", end=" ")
pdf_path = out_dir / "test_法規検討計算書.pdf"
generate_pdf(site, far_result, road_slope, adj_slope, shadow, boundary, pdf_path)
print(f"OK → {pdf_path}")

print()
print("テスト完了")
