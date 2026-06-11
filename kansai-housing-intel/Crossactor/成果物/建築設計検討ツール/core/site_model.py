"""敷地データモデル"""
from dataclasses import dataclass, field
from typing import Optional
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

from core.law_database import ZoneInfo, ZONE_REGULATIONS, CIVIL_CODE_BOUNDARY_DISTANCE


def _normalize_zone_name(raw: str) -> str:
    if not raw:
        return "第一種住居地域"
    if raw in ZONE_REGULATIONS:
        return raw
    for key in ZONE_REGULATIONS:
        if key in raw:
            return key
    ALIASES = {
        "1住": "第一種住居地域", "2住": "第二種住居地域",
        "1低": "第一種低層住居専用地域", "2低": "第二種低層住居専用地域",
        "1中": "第一種中高層住居専用地域", "2中": "第二種中高層住居専用地域",
        "準住": "準住居地域", "近商": "近隣商業地域", "商業": "商業地域",
        "準工": "準工業地域", "工業": "工業地域", "工専": "工業専用地域",
    }
    for alias, zone in ALIASES.items():
        if alias in raw:
            return zone
    print(f"[警告] 用途地域を特定できませんでした: '{raw}' → 第一種住居地域 として処理")
    return "第一種住居地域"


def _swap_yx(coords: list) -> list:
    """測量座標の Y,X 順を Shapely の X,Y 順に変換する"""
    return [(c[1], c[0]) for c in coords]


def _merge_polygons(parcel_list: list[dict]) -> Optional[Polygon]:
    polys = []
    for parcel in parcel_list:
        coords = parcel.get("境界座標")
        if coords and len(coords) >= 3:
            polys.append(Polygon(_swap_yx(coords)))
    if not polys:
        return None
    merged = unary_union(polys)
    if isinstance(merged, MultiPolygon):
        merged = max(merged.geoms, key=lambda p: p.area)
    return merged


@dataclass
class Road:
    width_m: float
    direction: str


@dataclass
class SiteModel:
    address: str
    zone_info: ZoneInfo
    site_area_m2: float
    polygon: Optional[Polygon]
    parcel_numbers: list[str] = field(default_factory=list)
    roads: list[Road] = field(default_factory=list)
    fire_zone: Optional[str] = None
    _buildable_polygon: Optional[Polygon] = field(default=None, repr=False)

    @classmethod
    def from_parsed(cls, data: dict, road_width_override: Optional[float] = None) -> "SiteModel":
        zone_name = _normalize_zone_name(data.get("用途地域") or "")
        zone_info = ZoneInfo.from_zone_name(
            zone_name,
            coverage_override=data.get("建蔽率"),
            far_override=data.get("容積率"),
        )

        parcels = data.get("筆") or []
        parcel_numbers = [p.get("地番", "") for p in parcels]

        area = sum(float(p.get("敷地面積_m2") or 0) for p in parcels)
        if area == 0:
            area = float(data.get("敷地面積_m2") or 0)

        polygon = _merge_polygons(parcels)
        if polygon is None:
            coords = data.get("敷地_境界座標")
            if coords and len(coords) >= 3:
                polygon = Polygon(_swap_yx(coords))

        road_width = road_width_override or data.get("前面道路_幅員_m")
        roads = []
        if road_width:
            roads.append(Road(
                width_m=float(road_width),
                direction=data.get("前面道路_方位") or "南",
            ))

        return cls(
            address=data.get("所在地", ""),
            zone_info=zone_info,
            site_area_m2=area,
            polygon=polygon,
            parcel_numbers=parcel_numbers,
            roads=roads,
            fire_zone=data.get("防火地域"),
        )

    def buildable_polygon(self, boundary_offset: float = CIVIL_CODE_BOUNDARY_DISTANCE) -> Optional[Polygon]:
        if self.polygon is None:
            return None
        if self._buildable_polygon is None:
            self._buildable_polygon = self.polygon.buffer(-boundary_offset)
        return self._buildable_polygon

    @property
    def main_road(self) -> Optional[Road]:
        if not self.roads:
            return None
        return max(self.roads, key=lambda r: r.width_m)
