"""建蔽率・容積率の計算（建築基準法第52・53条）"""
from dataclasses import dataclass
from core.site_model import SiteModel


@dataclass
class CoverageFARResult:
    max_coverage_ratio: float
    max_building_area_m2: float
    max_far: float
    max_total_floor_area_m2: float
    road_far_limit: float
    effective_far: float
    effective_total_floor_area_m2: float
    fire_zone_bonus: float
    notes: list[str]


def calculate_coverage_far(site: SiteModel) -> CoverageFARResult:
    notes = []
    zone = site.zone_info
    coverage = zone.coverage_ratio
    fire_bonus = 0.0

    if site.fire_zone == "防火地域":
        fire_bonus += 0.10
        notes.append("防火地域内の耐火建築物: 建蔽率+10%")
    elif site.fire_zone == "準防火地域":
        fire_bonus += 0.10
        notes.append("準防火地域内の準耐火建築物: 建蔽率+10%")

    if zone.zone_name == "商業地域" and coverage == 0.80 and site.fire_zone == "防火地域":
        coverage = 1.00
        fire_bonus = 0.0
        notes.append("商業地域・防火地域・耐火建築物: 建蔽率制限なし")

    effective_coverage = min(coverage + fire_bonus, 1.00)
    max_building_area = site.site_area_m2 * effective_coverage

    far = zone.floor_area_ratio
    road_far = far

    if site.main_road:
        w = site.main_road.width_m
        if "住居" in zone.zone_name or zone.zone_name == "準住居地域":
            road_far = w * 0.40
        else:
            road_far = w * 0.60
        if road_far < far:
            notes.append(f"前面道路幅員{w}m による容積率制限: {road_far*100:.0f}%")

    effective_far = min(far, road_far)

    return CoverageFARResult(
        max_coverage_ratio=effective_coverage,
        max_building_area_m2=max_building_area,
        max_far=far,
        max_total_floor_area_m2=site.site_area_m2 * far,
        road_far_limit=road_far,
        effective_far=effective_far,
        effective_total_floor_area_m2=site.site_area_m2 * effective_far,
        fire_zone_bonus=fire_bonus,
        notes=notes,
    )
