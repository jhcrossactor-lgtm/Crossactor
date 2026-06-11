"""ezdxf を使って設計検討図をDXFとして出力する"""
import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment
from pathlib import Path
from typing import Optional
from shapely.geometry import Polygon, LineString

from core.site_model import SiteModel
from core.boundary_classifier import BoundaryEdge, extract_edges
from calculations.coverage_far import CoverageFARResult
from calculations.setback_shadow import RoadSlopeResult
from calculations.road_slope_envelope import SlopeEnvelopeLine, build_road_slope_envelope


LAYERS = {
    "敷地境界":       {"color": colors.WHITE},
    "道路境界":        {"color": colors.YELLOW},
    "隣地境界":        {"color": colors.WHITE},
    "建築可能範囲":    {"color": colors.CYAN},
    "道路斜線_等高線":  {"color": colors.RED},
    "道路斜線_限界線":  {"color": 1},
    "道路斜線_注記":    {"color": colors.RED},
    "隣地斜線":        {"color": colors.MAGENTA},
    "日影5m":          {"color": colors.YELLOW},
    "日影10m":         {"color": colors.GREEN},
    "テキスト":        {"color": colors.WHITE},
    "境界番号":        {"color": colors.YELLOW},
}


def _setup_layers(doc):
    for name, props in LAYERS.items():
        layer = doc.layers.new(name) if name not in doc.layers else doc.layers.get(name)
        layer.color = props["color"]


def _polygon_to_dxf(msp, polygon: Polygon, layer: str) -> None:
    msp.add_lwpolyline(list(polygon.exterior.coords), dxfattribs={"layer": layer, "closed": True})


def _linestring_to_dxf(msp, line: LineString, layer: str) -> None:
    if len(list(line.coords)) >= 2:
        msp.add_lwpolyline(list(line.coords), dxfattribs={"layer": layer})


def _add_text(msp, text: str, x: float, y: float, height: float = 0.5, layer: str = "テキスト") -> None:
    msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(
        (x, y), align=TextEntityAlignment.LEFT)


def _draw_slope_envelopes(msp, envelopes: list[SlopeEnvelopeLine]) -> None:
    for env in envelopes:
        layer = "道路斜線_限界線" if env.is_limit_boundary else "道路斜線_等高線"
        _linestring_to_dxf(msp, env.line, layer)
        mid = env.line.interpolate(0.5, normalized=True)
        label = (f"H≦{env.height_m:.0f}m" if not env.is_limit_boundary
                 else f"斜線限界({env.distance_from_road_m:.0f}m)")
        _add_text(msp, label, mid.x + 0.3, mid.y + 0.3, height=0.5, layer="道路斜線_注記")


def _draw_boundary_edges(msp, edges: list[BoundaryEdge]) -> None:
    """道路・隣地別に色分けして境界線を描画"""
    for e in edges:
        layer = "道路境界" if e.kind == "道路" else "隣地境界"
        _linestring_to_dxf(msp, e.line, layer)
        # 番号ラベル
        mid = e.midpoint
        sx, sy = e.start
        ex, ey = e.end
        dx, dy = ey - sy, -(ex - sx)
        length = (dx**2 + dy**2) ** 0.5
        offset = e.length_m * 0.05
        nx, ny = (dx / length * offset, dy / length * offset) if length > 0 else (offset, offset)
        _add_text(msp, str(e.index), mid.x + nx, mid.y + ny, height=offset * 3, layer="境界番号")


def generate_boundary_check_dxf(polygon: Polygon, output_path: str | Path) -> Path:
    """境界確認用DXF（番号付き）"""
    output_path = Path(output_path)
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    _setup_layers(doc)
    msp = doc.modelspace()

    edges = extract_edges(polygon)
    bounds = polygon.bounds
    offset = (bounds[2] - bounds[0]) * 0.03

    for e in edges:
        msp.add_lwpolyline(list(e.line.coords), dxfattribs={"layer": "敷地境界"})
        mid = e.midpoint
        sx, sy = e.start
        ex, ey = e.end
        dx, dy = ey - sy, -(ex - sx)
        length = (dx**2 + dy**2) ** 0.5
        nx, ny = (dx / length * offset, dy / length * offset) if length > 0 else (offset, offset)

        msp.add_text(str(e.index),
                     dxfattribs={"layer": "境界番号", "height": offset * 2.5,
                                 "color": colors.YELLOW}).set_placement(
            (mid.x + nx, mid.y + ny), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(f"{e.length_m:.2f}m",
                     dxfattribs={"layer": "テキスト", "height": offset * 1.5,
                                 "color": colors.CYAN}).set_placement(
            (mid.x + nx * 2, mid.y + ny * 2 - offset * 2.5),
            align=TextEntityAlignment.MIDDLE_CENTER)

    doc.saveas(str(output_path))
    return output_path


def generate_dxf(
    site: SiteModel,
    far_result: CoverageFARResult,
    road_slope: Optional[RoadSlopeResult],
    output_path: str | Path,
    edges: list[BoundaryEdge] | None = None,
) -> Path:
    output_path = Path(output_path)
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    _setup_layers(doc)
    msp = doc.modelspace()

    if site.polygon:
        # 境界線（色分け）
        if edges:
            _draw_boundary_edges(msp, edges)
        else:
            _polygon_to_dxf(msp, site.polygon, "敷地境界")

        # 建築可能範囲
        buildable = site.buildable_polygon()
        if buildable and not buildable.is_empty:
            _polygon_to_dxf(msp, buildable, "建築可能範囲")

        # 道路斜線等高線
        envelopes = build_road_slope_envelope(site)
        if envelopes:
            _draw_slope_envelopes(msp, envelopes)

        # テキスト注記
        bounds = site.polygon.bounds
        text_x, text_y = bounds[0], bounds[3] + 2.0
        parcels = " + ".join(site.parcel_numbers) if site.parcel_numbers else ""
        lines = [
            f"所在地: {site.address}  地番: {parcels}",
            f"用途地域: {site.zone_info.zone_name}  防火地域: {site.fire_zone or 'なし'}",
            f"敷地面積: {site.site_area_m2:.2f}m²",
            f"建蔽率: {far_result.max_coverage_ratio*100:.0f}%  最大建築面積: {far_result.max_building_area_m2:.1f}m²",
            f"容積率（有効）: {far_result.effective_far*100:.0f}%  最大延床面積: {far_result.effective_total_floor_area_m2:.1f}m²",
        ]
        if road_slope and road_slope.road_width_m:
            lines.append(f"道路斜線: 勾配1:{road_slope.slope_ratio}  境界最大高さ {road_slope.max_height_at_boundary_m:.1f}m")
        for i, line in enumerate(lines):
            _add_text(msp, line, text_x, text_y - i * 1.2, height=0.6)
    else:
        _add_text(msp, f"敷地面積: {site.site_area_m2:.2f}m²", 0, 10)
        _add_text(msp, f"用途地域: {site.zone_info.zone_name}", 0, 8)

    doc.saveas(str(output_path))
    return output_path
