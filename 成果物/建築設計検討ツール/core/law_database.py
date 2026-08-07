"""建築基準法の数値テーブルを構造化して保持する（e-Gov条文を正典として管理）"""
from dataclasses import dataclass
from typing import Optional

# 建築基準法第53条 / 第52条 用途地域別制限値
ZONE_REGULATIONS: dict[str, dict] = {
    "第一種低層住居専用地域": {
        "建蔽率_max": 0.60, "容積率_max": 2.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 1.5, "隣地斜線_適用": False,
    },
    "第二種低層住居専用地域": {
        "建蔽率_max": 0.60, "容積率_max": 2.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 1.5, "隣地斜線_適用": False,
    },
    "第一種中高層住居専用地域": {
        "建蔽率_max": 0.60, "容積率_max": 5.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 20.0, "隣地斜線_勾配": 1.25,
    },
    "第二種中高層住居専用地域": {
        "建蔽率_max": 0.60, "容積率_max": 5.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 20.0, "隣地斜線_勾配": 1.25,
    },
    "第一種住居地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 20.0, "隣地斜線_勾配": 1.25,
    },
    "第二種住居地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 20.0, "隣地斜線_勾配": 1.25,
    },
    "準住居地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.25,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 20.0, "隣地斜線_勾配": 1.25,
    },
    "近隣商業地域": {
        "建蔽率_max": 0.80, "容積率_max": 4.00, "道路斜線_勾配": 1.50,
        "日影規制_対象": False, "隣地斜線_適用": True,
        "隣地斜線_基点高": 31.0, "隣地斜線_勾配": 2.50,
    },
    "商業地域": {
        "建蔽率_max": 0.80, "容積率_max": 13.00, "道路斜線_勾配": 1.50,
        "日影規制_対象": False, "隣地斜線_適用": True,
        "隣地斜線_基点高": 31.0, "隣地斜線_勾配": 2.50,
    },
    "準工業地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.50,
        "日影規制_対象": True, "日影_測定面": 4.0, "隣地斜線_適用": True,
        "隣地斜線_基点高": 31.0, "隣地斜線_勾配": 2.50,
    },
    "工業地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.50,
        "日影規制_対象": False, "隣地斜線_適用": True,
        "隣地斜線_基点高": 31.0, "隣地斜線_勾配": 2.50,
    },
    "工業専用地域": {
        "建蔽率_max": 0.60, "容積率_max": 4.00, "道路斜線_勾配": 1.50,
        "日影規制_対象": False, "隣地斜線_適用": True,
        "隣地斜線_基点高": 31.0, "隣地斜線_勾配": 2.50,
    },
}

SHADOW_REGULATIONS: dict[str, dict] = {
    "第一種低層住居専用地域": {
        "軒高7m超または3階以上": {"5m_line": 3, "10m_line": 2},
        "高さ10m超":             {"5m_line": 4, "10m_line": 2.5},
    },
    "第二種低層住居専用地域": {
        "軒高7m超または3階以上": {"5m_line": 3, "10m_line": 2},
        "高さ10m超":             {"5m_line": 4, "10m_line": 2.5},
    },
    "第一種中高層住居専用地域": {"高さ10m超": {"5m_line": 3, "10m_line": 2}},
    "第二種中高層住居専用地域": {"高さ10m超": {"5m_line": 3, "10m_line": 2}},
    "第一種住居地域":           {"高さ10m超": {"5m_line": 4, "10m_line": 2.5}},
    "第二種住居地域":           {"高さ10m超": {"5m_line": 4, "10m_line": 2.5}},
    "準住居地域":               {"高さ10m超": {"5m_line": 4, "10m_line": 2.5}},
    "準工業地域":               {"高さ10m超": {"5m_line": 4, "10m_line": 2.5}},
}

CIVIL_CODE_BOUNDARY_DISTANCE = 0.50


@dataclass
class ZoneInfo:
    zone_name: str
    coverage_ratio: float
    floor_area_ratio: float
    road_slope_ratio: float
    shadow_regulated: bool
    shadow_measurement_height: float = 4.0
    adjacent_slope_applicable: bool = False
    adjacent_slope_base_height: float = 20.0
    adjacent_slope_ratio: float = 1.25
    fire_zone: Optional[str] = None

    @classmethod
    def from_zone_name(cls, zone_name: str,
                       coverage_override: Optional[float] = None,
                       far_override: Optional[float] = None) -> "ZoneInfo":
        reg = ZONE_REGULATIONS[zone_name]
        return cls(
            zone_name=zone_name,
            coverage_ratio=coverage_override or reg["建蔽率_max"],
            floor_area_ratio=far_override or reg["容積率_max"],
            road_slope_ratio=reg["道路斜線_勾配"],
            shadow_regulated=reg["日影規制_対象"],
            shadow_measurement_height=reg.get("日影_測定面", 4.0),
            adjacent_slope_applicable=reg.get("隣地斜線_適用", False),
            adjacent_slope_base_height=reg.get("隣地斜線_基点高", 20.0),
            adjacent_slope_ratio=reg.get("隣地斜線_勾配", 1.25),
        )
