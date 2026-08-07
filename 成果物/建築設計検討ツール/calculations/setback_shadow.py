"""道路斜線・隣地斜線・日影規制の計算（建築基準法第56条・第56条の2）"""
from dataclasses import dataclass
from core.site_model import SiteModel
from core.law_database import SHADOW_REGULATIONS


@dataclass
class RoadSlopeResult:
    road_width_m: float
    slope_ratio: float
    setback_from_road_m: float
    max_height_at_boundary_m: float
    applicable_distance_m: float
    notes: list[str]


@dataclass
class AdjacentSlopeResult:
    base_height_m: float
    slope_ratio: float
    notes: list[str]


@dataclass
class ShadowResult:
    regulated: bool
    measurement_height_m: float
    limit_5m: float
    limit_10m: float
    trigger: str
    notes: list[str]


def calc_road_slope(site: SiteModel, building_height_m: float) -> RoadSlopeResult:
    notes = []
    zone = site.zone_info
    road = site.main_road

    if road is None:
        return RoadSlopeResult(0, zone.road_slope_ratio, 0, 0, 0, ["前面道路データなし"])

    w = road.width_m
    ratio = zone.road_slope_ratio
    max_horizontal = 20.0 if ("住居" in zone.zone_name or zone.zone_name == "準住居地域") else 35.0
    max_height_at_boundary = w * ratio

    if building_height_m > max_height_at_boundary:
        distance_needed = building_height_m / ratio - w
        notes.append(
            f"建物高さ {building_height_m}m は道路境界での制限 {max_height_at_boundary}m を超過。"
            f"道路から {distance_needed:.1f}m 以上セットバックが必要。"
        )
    else:
        notes.append(f"道路斜線 OK: 高さ {building_height_m}m ≤ 制限 {max_height_at_boundary}m")

    return RoadSlopeResult(
        road_width_m=w, slope_ratio=ratio, setback_from_road_m=0,
        max_height_at_boundary_m=max_height_at_boundary,
        applicable_distance_m=max_horizontal, notes=notes,
    )


def calc_adjacent_slope(site: SiteModel, building_height_m: float) -> AdjacentSlopeResult:
    notes = []
    zone = site.zone_info
    if not zone.adjacent_slope_applicable:
        return AdjacentSlopeResult(0, 0, ["隣地斜線制限 対象外（低層住居専用地域）"])

    base_h = zone.adjacent_slope_base_height
    ratio = zone.adjacent_slope_ratio
    if building_height_m > base_h:
        distance_needed = (building_height_m - base_h) / ratio
        notes.append(f"隣地斜線: 境界での制限 {base_h}m を超過。境界から {distance_needed:.1f}m のセットバックが必要。")
    else:
        notes.append(f"隣地斜線 OK: 高さ {building_height_m}m ≤ 境界制限 {base_h}m")

    return AdjacentSlopeResult(base_height_m=base_h, slope_ratio=ratio, notes=notes)


def calc_shadow(site: SiteModel, building_height_m: float,
                eave_height_m: float, floors: int) -> ShadowResult:
    notes = []
    zone = site.zone_info
    zone_name = zone.zone_name

    if not zone.shadow_regulated:
        return ShadowResult(False, 0, 0, 0, "", ["日影規制 対象外用途地域"])

    measurement_h = zone.shadow_measurement_height
    shadow_reg = SHADOW_REGULATIONS.get(zone_name, {})
    trigger = ""
    limits = {}

    if "低層" in zone_name:
        if eave_height_m > 7.0 or floors >= 3:
            trigger = "軒高7m超または3階以上"
            limits = shadow_reg.get(trigger, {})
        if building_height_m > 10.0:
            trigger = "高さ10m超"
            limits = shadow_reg.get(trigger, limits)
    else:
        if building_height_m > 10.0:
            trigger = "高さ10m超"
            limits = shadow_reg.get(trigger, {})

    if not trigger:
        return ShadowResult(False, measurement_h, 0, 0, "", ["日影規制の対象となる建物規模に該当しない"])

    limit_5 = limits.get("5m_line", 0)
    limit_10 = limits.get("10m_line", 0)
    notes = [
        f"日影規制対象: {trigger}",
        f"測定面高さ: {measurement_h}m",
        f"5m ライン: {limit_5}時間以内 / 10m ライン: {limit_10}時間以内",
    ]
    return ShadowResult(True, measurement_h, limit_5, limit_10, trigger, notes)


def calc_boundary_distance(site: SiteModel) -> dict:
    return {
        "required_distance_m": 0.50,
        "law_reference": "民法第234条",
        "note": "建物は隣地境界線から50cm以上離す必要があります。",
    }
