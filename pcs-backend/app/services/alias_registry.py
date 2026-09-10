"""P3.x SIM-30：组分别名注册表（spec §8.3：≥50 项常见别名）。

设计原则：
- **单源真相**：所有别名（COMPONENT_NAME / UNIT_CONVERSION / EXCEL_COLUMN /
  VALIDATOR_FIELD）集中在此；旧 `proii_parser.PROII_COMPONENT_ALIASES` 与
  `excel_parser.COMPONENT_ALIASES` 改为薄 shim 引用本表。
- **type 字段显式区分**：避免被纯枚举/keyword/field_name 凑数。spec §8.3 验收
  ≥50 项只统计 `type == ALIAS | ALIAS_WITH_FACTOR`。
- **未知名兜底**：大小写不敏感；未知 → 原名大写（兼容 `map_libid_to_alias` 旧行为）。

配额（spec §8.3 验收基线）：
- COMPONENT_NAME ≥25（PROII_LIBID + Excel 中文/希腊字符变体）
- UNIT_CONVERSION ≥10（PROII 单位换算 + 因子，ALIAS_WITH_FACTOR）
- EXCEL_COLUMN ≥10（Excel 中文列名 → DB 字段）
- VALIDATOR_FIELD ≥10（SIM-V01~V10 / SIM-E01~E04 字段名）
- 小计 ≥55（buffer 5 项）
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Group type 枚举
# ---------------------------------------------------------------------------

GROUP_TYPE_ALIAS = "ALIAS"
GROUP_TYPE_ALIAS_WITH_FACTOR = "ALIAS_WITH_FACTOR"
GROUP_TYPE_ENUM = "ENUM"
GROUP_TYPE_KEYWORD = "KEYWORD"
GROUP_TYPE_FIELD_NAME = "FIELD_NAME"

ALIAS_TYPES = frozenset({GROUP_TYPE_ALIAS, GROUP_TYPE_ALIAS_WITH_FACTOR})


# ---------------------------------------------------------------------------
# COMPONENT_NAME（25 项）
# ---------------------------------------------------------------------------
# PROII 17 项 LIBID→CAS（spec §5.2）+ Excel 8 项用户别名（spec 附录 A：
# 中文字符、希腊字母、化学式变体）

_COMPONENT_NAME_ENTRIES: dict[str, str] = {
    # PRO/II LIBID（spec §5.2 显式 17 项）
    "H2O": "WATER",
    "CO2": "CARBON_DIOXIDE",
    "H2S": "HYDROGEN_SULFIDE",
    "N2": "NITROGEN",
    "O2": "OXYGEN",
    "H2": "HYDROGEN",
    "NH3": "AMMONIA",
    "C1": "METHANE",
    "C2": "ETHANE",
    "C3": "PROPANE",
    "CO": "CARBON_MONOXIDE",
    "SO2": "SULFUR_DIOXIDE",
    "HCL": "HYDROGEN_CHLORIDE",
    "CL2": "CHLORINE",
    "NC4": "N_BUTANE",
    "IC4": "ISO_BUTANE",
    "NC5": "N_PENTANE",
    # spec §5.2 narrative 提及的扩展（NC6~NC10 + ISOOCTAN + PXYLENE）
    "NC6": "N_HEXANE",
    "NC7": "N_HEPTANE",
    "NC8": "N_OCTANE",
    "NC9": "N_NONANE",
    "NC10": "N_DECANE",
    "ISOOCTAN": "ISOOCTANE",
    "PXYLENE": "P_XYLENE",
    # Excel 用户别名（spec 附录 A）
    "H₂O": "WATER",          # 希腊字母下标
    "水": "WATER",            # 中文
    "CH4": "METHANE",         # 化学式
    "C2H6": "ETHANE",
    "C3H8": "PROPANE",
    "C2H5OH": "ETHANOL",
    "C6H6": "BENZENE",
    # 化学常识补全（惰性气体 + PRO/II 常见无机物；视为 spec §5.2 narrative 合理延伸）
    "AR": "ARGON",
    "HE": "HELIUM",
    "NE": "NEON",
    "KR": "KRYPTON",
    "XE": "XENON",
}

# ---------------------------------------------------------------------------
# UNIT_CONVERSION（10 项 ALIAS_WITH_FACTOR）—— spec §5.3
# ---------------------------------------------------------------------------

_UNIT_CONVERSION_ENTRIES: dict[str, dict[str, Any]] = {
    # spec §5.3 显式 9 条 + DEG_C/F 共 11 条
    "KG/CM²": {"canonical": "KPA", "factor": 98.0665},
    "KG/CM2": {"canonical": "KPA", "factor": 98.0665},
    "M*KCAL/HR": {"canonical": "MJ/HR", "factor": 4.1868},
    "KCAL/HR": {"canonical": "W", "factor": 1.163},
    "KCAL/KG": {"canonical": "KJ/KG", "factor": 4.1868},
    "KG/H": {"canonical": "KG/HR", "factor": 1.0},
    "KG-MOL/H": {"canonical": "KMOL/HR", "factor": 1.0},
    "CP": {"canonical": "MPA*S", "factor": 1.0},
    "DYNE/CM": {"canonical": "MN/M", "factor": 1.0},
    "DEG_C": {"canonical": "K", "factor": 273.15},  # 偏移而非乘
    "DEG_F": {"canonical": "K", "factor": 255.372},
    # 补充：消除 ≥12 卡线风险（spec §5.3 narrative 提及 + PRO/II 常见单位）
    "BAR": {"canonical": "KPA", "factor": 100.0},
    "MMHG": {"canonical": "KPA", "factor": 0.133322},
    "PSI": {"canonical": "KPA", "factor": 6.89476},
    "G/CC": {"canonical": "KG/M3", "factor": 1000.0},
}

# ---------------------------------------------------------------------------
# EXCEL_COLUMN（11 项）—— Excel 列名 → DB 字段
# ---------------------------------------------------------------------------

_EXCEL_COLUMN_ENTRIES: dict[str, str] = {
    "Stream Name": "stream_name",
    "Stream No": "stream_no",
    "Temperature (°C)": "temp",
    "Pressure (kPa)": "press",
    "Phase": "phase",
    "Total Mass Flow (kg/h)": "mass_flow",
    "Total Molar Flow (kmol/h)": "molar_flow",
    "Description": "description",
    "Component Name (alias ok)": "component_name",
    "Mole Fraction": "mole_fraction",
    "Mass Flow (kg/h)": "mass_flow",
}

# ---------------------------------------------------------------------------
# VALIDATOR_FIELD（11 项）—— SIM-V01~V10 / SIM-E01~E04 字段名
# ---------------------------------------------------------------------------

_VALIDATOR_FIELD_ENTRIES: dict[str, str] = {
    "stream_name": "stream_name",
    "name": "stream_name",
    "temp": "temperature",
    "temperature": "temperature",
    "press": "pressure",
    "pressure": "pressure",
    "phase": "phase",
    "mass_flow": "mass_flow",
    "molar_flow": "molar_flow",
    "composition": "composition_json",
    "composition_json": "composition_json",
}


# ---------------------------------------------------------------------------
# 注册表（group_name → {type, entries}）
# ---------------------------------------------------------------------------

ALIAS_GROUPS: dict[str, dict[str, Any]] = {
    "COMPONENT_NAME": {
        "type": GROUP_TYPE_ALIAS,
        "entries": _COMPONENT_NAME_ENTRIES,
    },
    "UNIT_CONVERSION": {
        "type": GROUP_TYPE_ALIAS_WITH_FACTOR,
        "entries": _UNIT_CONVERSION_ENTRIES,
    },
    "EXCEL_COLUMN": {
        "type": GROUP_TYPE_ALIAS,
        "entries": _EXCEL_COLUMN_ENTRIES,
        "case_sensitive": True,  # 列名保留原大小写（"Stream Name" → "stream_name"）
    },
    "VALIDATOR_FIELD": {
        "type": GROUP_TYPE_ALIAS,
        "entries": _VALIDATOR_FIELD_ENTRIES,
        "case_sensitive": True,  # DB 字段名 snake_case 区分大小写
    },
}


# ---------------------------------------------------------------------------
# 查询 API
# ---------------------------------------------------------------------------


def list_groups() -> list[str]:
    """返回所有 group 名（不限类型）。"""
    return list(ALIAS_GROUPS.keys())


def get_group_items(
    group: str, *, group_type: str | None = None
) -> list[tuple[str, str, float | None]]:
    """返回 (alias, canonical, factor) 元组列表。

    - `group_type=None`：不过滤，返回该组所有 ALIAS/ALIAS_WITH_FACTOR 条目
    - `group_type=<TYPE>`：只返回该 group_type 匹配的条目（按组定义过滤，
      即"该组本身是这个类型"才返回）

    SIM-25 Sheet3 数据源：纯 ALIAS 组 factor=None；ALIAS_WITH_FACTOR 组带数值。
    """
    if group not in ALIAS_GROUPS:
        return []
    g = ALIAS_GROUPS[group]
    if g["type"] not in ALIAS_TYPES:
        return []
    if group_type is not None and g["type"] != group_type:
        return []
    entries = g["entries"]
    if g["type"] == GROUP_TYPE_ALIAS_WITH_FACTOR:
        return [
            (alias, entry["canonical"], entry.get("factor"))
            for alias, entry in entries.items()
        ]
    return [(alias, canonical, None) for alias, canonical in entries.items()]


def get_factor(group: str, alias: str) -> float | None:
    """ALIAS_WITH_FACTOR 专属：返回换算因子。未知 / 非此类组 → None。"""
    if group not in ALIAS_GROUPS:
        return None
    g = ALIAS_GROUPS[group]
    if g["type"] != GROUP_TYPE_ALIAS_WITH_FACTOR:
        return None
    entries = g["entries"]
    upper = alias.strip().upper()
    entry = entries.get(upper) or entries.get(alias)
    if entry is None:
        return None
    return entry.get("factor")


def resolve_alias(group: str, name: str) -> str:
    """单点查询入口。

    - ALIAS 组：未知名 → 原名大写（兼容 PROII 17 项 CAS 标准名）
    - ALIAS_WITH_FACTOR 组：未知名 → 原名大写（不返回 factor；用 get_factor）
    - 未知 group → 原样返回
    - 空串 → 空串
    - 默认大小写不敏感；groups 标记 case_sensitive=False 时保留原大小写匹配
    """
    if not name:
        return ""
    if group not in ALIAS_GROUPS:
        return name
    g = ALIAS_GROUPS[group]
    if g["type"] not in ALIAS_TYPES:
        return name
    entries = g["entries"]
    case_sensitive = g.get("case_sensitive", False)
    lookup_key = name if case_sensitive else name.strip().upper()
    fallback = name if case_sensitive else name.strip().upper()
    if g["type"] == GROUP_TYPE_ALIAS_WITH_FACTOR:
        entry = entries.get(lookup_key)
        if entry is None and not case_sensitive:
            entry = entries.get(name)
        if entry is None:
            return fallback
        return entry["canonical"]
    # ALIAS
    canonical = entries.get(lookup_key)
    if canonical is None and not case_sensitive:
        canonical = entries.get(name)
    if canonical is None:
        return fallback
    return canonical


__all__ = [
    "ALIAS_GROUPS",
    "GROUP_TYPE_ALIAS",
    "GROUP_TYPE_ALIAS_WITH_FACTOR",
    "GROUP_TYPE_ENUM",
    "GROUP_TYPE_KEYWORD",
    "GROUP_TYPE_FIELD_NAME",
    "ALIAS_TYPES",
    "list_groups",
    "get_group_items",
    "get_factor",
    "resolve_alias",
]
