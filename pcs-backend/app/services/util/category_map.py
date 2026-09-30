"""S1-5 R4/R2: 13 类公用工程枚举 + 单位 + 13→6 fuel_type 映射。

Per SPEC V1.4 §4.4（公用工程分类）：
  5 类能源：ELECTRICITY / STEAM_HP / STEAM_MP / STEAM_LP / FUEL_GAS
  + CONDENSATE (蒸汽冷凝水，按 STEAM 折标)
  + 7 类非能源公用工程：COOLING_WATER / CHILLED_WATER / MAKEUP_WATER /
    NITROGEN / INSTRUMENT_AIR / PLANT_AIR

13 = 5 + 4 STEAM 子类 + 1 CONDENSATE + 6 + TOTAL_PLACEHOLDER = 13 keys
（其中 1 个为占位总计，不参与折算；实际 12 类为业务类）。

映射到 ToeConversionFactor 6 fuel_type（GAS/DIESEL/COAL/STEAM/
ELECTRICITY/OTHER）：
  ELECTRICITY → ELECTRICITY (TOE 0.1229)
  STEAM_HP/MP/LP + CONDENSATE → STEAM (TOE 0.1429)
  FUEL_GAS → GAS (TOE 1.0000)
  其他 7 类 → None（无 TOE 折算，纯 utility 计数）
"""

from __future__ import annotations

from enum import Enum


class UtilityCategory(str, Enum):
    """13 类公用工程（per SPEC V1.4 §4.4）。"""

    ELECTRICITY = "ELECTRICITY"
    STEAM_HP = "STEAM_HP"          # 高压蒸汽 (≥ 4.0 MPa)
    STEAM_MP = "STEAM_MP"          # 中压蒸汽 (1.0-4.0 MPa)
    STEAM_LP = "STEAM_LP"          # 低压蒸汽 (0.1-1.0 MPa)
    CONDENSATE = "CONDENSATE"      # 蒸汽冷凝水
    COOLING_WATER = "COOLING_WATER"
    CHILLED_WATER = "CHILLED_WATER"
    MAKEUP_WATER = "MAKEUP_WATER"
    FUEL_GAS = "FUEL_GAS"
    NITROGEN = "NITROGEN"
    INSTRUMENT_AIR = "INSTRUMENT_AIR"
    PLANT_AIR = "PLANT_AIR"
    TOTAL = "TOTAL"                # 占位（汇总字段）


# R3 flat: 单位由字典维护（每类一个单位，避免 nested schema）
UNIT_BY_CATEGORY: dict[str, str] = {
    "ELECTRICITY": "kWh",
    "STEAM_HP": "t/h",
    "STEAM_MP": "t/h",
    "STEAM_LP": "t/h",
    "CONDENSATE": "t/h",
    "COOLING_WATER": "t/h",
    "CHILLED_WATER": "t/h",
    "MAKEUP_WATER": "t/h",
    "FUEL_GAS": "Nm3/h",
    "NITROGEN": "Nm3/h",
    "INSTRUMENT_AIR": "Nm3/h",
    "PLANT_AIR": "Nm3/h",
    "TOTAL": "",
}


# R2: 13 类 → 6 fuel_type 映射（仅能源类有 TOE；非能源 → None）
TOE_FUEL_TYPE_BY_CATEGORY: dict[str, str | None] = {
    "ELECTRICITY": "ELECTRICITY",
    "STEAM_HP": "STEAM",
    "STEAM_MP": "STEAM",
    "STEAM_LP": "STEAM",
    "CONDENSATE": "STEAM",
    "COOLING_WATER": None,
    "CHILLED_WATER": None,
    "MAKEUP_WATER": None,
    "FUEL_GAS": "GAS",
    "NITROGEN": None,
    "INSTRUMENT_AIR": None,
    "PLANT_AIR": None,
    "TOTAL": None,  # 占位不参与
}


def utility_categories() -> list[UtilityCategory]:
    """返回 13 类枚举值列表（顺序 = UtilityCategory 定义顺序）。"""
    return list(UtilityCategory)
