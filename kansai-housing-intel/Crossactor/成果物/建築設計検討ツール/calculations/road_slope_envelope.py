"""道路斜線の包絡線（等高線）を生成する（建築基準法第56条第1項第1号）"""
from dataclasses import dataclass
from shapely.geometry import LineString, Polygon
from shapely.validation import make_valid

from core.site_model import SiteModel


@dataclass
class SlopeEnvelopeLine:
    height_m: float
    distance_from_road_m: float
    line: LineString
    is_limit_boundary: bool = False


def _road_coord(polygon: Polygon, direction: str) -> float:
    minx, miny, maxx, maxy = polygon.bounds
    if "北" in direction: return maxy
    if "南" in direction: return miny
    if "東" in direction: return maxx
    return minx


def _make_offset_line(polygon: Polygon, direction: str, offset: float) -> LineString | None:
    minx, miny, maxx, maxy = polygon.bounds
    margin = 10.0
    road_coord = _road_coord(polygon, direction)

    if "北" in direction:
        cut_line = LineString([(minx - margin, road_coord - offset), (maxx + margin, road_coord - offset)])
    elif "南" in direction:
        cut_line = LineString([(minx - margin, road_coord + offset), (maxx + margin, road_coord + offset)])
    elif "東" in direction:
        cut_line = LineString([(road_coord - offset, miny - margin), (road_coord - offset, maxy + margin)])
    else:
        cut_line = LineString([(road_coord + offset, miny - margin), (road_coord + offset, maxy + margin)])

    clipped = cut_line.intersection(make_valid(polygon))
    if clipped.is_empty:
        return None
    if clipped.geom_type == "MultiLineString":
        return max(clipped.geoms, key=lambda l: l.length)
    return clipped if clipped.geom_type == "LineString" else None


def build_road_slope_envelope(site: SiteModel, height_step: float = 3.0) -> list[SlopeEnvelopeLine]:
    if site.polygon is None or not site.roads:
        return []

    road = site.main_road
    zone = site.zone_info
    slope = zone.road_slope_ratio
    road_w = road.width_m
    direction = road.direction
    max_distance = 20.0 if ("住居" in zone.zone_name or zone.zone_name == "準住居地域") else 35.0

    results = []
    h = height_step
    while True:
        d = h / slope - road_w
        if d < 0:
            h += height_step
            continue
        if d > max_distance:
            break
        line = _make_offset_line(site.polygon, direction, d)
        if line:
            results.append(SlopeEnvelopeLine(height_m=h, distance_from_road_m=d, line=line))
        h += height_step

    limit_line = _make_offset_line(site.polygon, direction, max_distance)
    if limit_line:
        results.append(SlopeEnvelopeLine(
            height_m=(road_w + max_distance) * slope,
            distance_from_road_m=max_distance,
            line=limit_line,
            is_limit_boundary=True,
        ))
    return results
