"""SUP-P5-PSV-002 V1.14 §3.3 API 526 孔口-法兰映射 + 变体 + 反向查询。

按 SPEC V1.14 §3.3：

- 14 项基础映射 D~T（API STD 526 第五版 Tables 2-15）
- G 孔口双档（1½G3 标准 + 2G3 高压）
- Q/R 变体（厂商可选）
- 反向映射：法兰尺寸 → 候选孔口列表
- get_candidate_orifices：法兰等级感知（1500#/2500# 仅允许 G 高压档）

设计要点：
- 与 app/services/psv/orifice_service.py 解耦：orifice_service 承载面积表（in²→m²），
  本模块承载孔口-法兰映射（不变量）
- API526_MIN_INLET 定义在 valve_selection_types.py；本模块 import 复用
- H/G 双候选场景（"2 inch × 3 inch"）：get_candidate_orifices 返回
  ["H", "G"]；前端按此过滤 override
- 法兰等级-孔口约束矩阵（84 组合）待 §8 gate #4 工艺工程师填入；
  本模块不实现 validate_flange_orifice（仅放 Warning 占位）

引用：
- API STD 526 第五版 Tables 2-15 原文（已附 SPEC §-1）
- V1.14 §-1 终结 G 孔口争议（1½G3 / 2G3 双档）
- V1.14 §3.3 全部映射常量（依据 SPEC 原文）
"""
from __future__ import annotations

import re
from typing import Final

from app.services.psv.valve_selection_types import (
    API526_MIN_INLET,
    PsvFlangeClass,
    PsvOrificeSize,
)

# ---------------------------------------------------------------------------
# §3.3.1 API 526 Tables 2-15 孔口-法兰基础映射
# ---------------------------------------------------------------------------

# ✅ 标准映射（API STD 526 第五版 Tables 2-15 原文）
#   字段：(inlet_size, outlet_size) — 字符串英寸
API526_ORIFICE_TO_FLANGE: Final[dict[PsvOrificeSize, tuple[str, str]]] = {
    "D": ("1 inch",   "2 inch"),        # Table 2  | 0.000710 in²
    "E": ("1.5 inch", "2.5 inch"),      # Table 3  | 0.001260 in²
    "F": ("1.5 inch", "2.5 inch"),      # Table 4  | 0.002010 in²
    "G": ("1.5 inch", "3 inch"),        # Table 5  | 0.003140 in² — 1½G3 标准档
    "H": ("2 inch",   "3 inch"),        # Table 6  | 0.004540 in²
    "J": ("3 inch",   "4 inch"),        # Table 7  | 0.006390 in²
    "K": ("3 inch",   "4 inch"),        # Table 8  | 0.009170 in²
    "L": ("4 inch",   "6 inch"),        # Table 9  | 0.013050 in²
    "M": ("4 inch",   "6 inch"),        # Table 10 | 0.017650 in²
    "N": ("4 inch",   "6 inch"),        # Table 11 | 0.024760 in²
    "P": ("6 inch",   "8 inch"),        # Table 12 | 0.033770 in²
    "Q": ("8 inch",   "10 inch"),       # Table 13 | 0.046330 in²
    "R": ("8 inch",   "10 inch"),       # Table 14 | 0.061720 in²
    "T": ("8 inch",   "10 inch"),       # Table 15 | 0.079170 in² — 8T10
}

# ✅ 高压档孔口（API 526 Table 5：2G3 1500#/2500#）
#   G 在高压档入口从 1.5" 升级到 2"（出口仍 3"）
API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE: Final[dict[PsvOrificeSize, tuple[str, str]]] = {
    "G": ("2 inch", "3 inch"),
}

# ✅ 厂商变体（V1.14 §3.3 末段；OPEN-13 待核验）
#   Q：8"×10"（标准） / 6"×8"（变体）
#   R：8"×10"（标准） / 6"×10"（变体）
API526_ORIFICE_VARIANTS: Final[dict[PsvOrificeSize, list[tuple[str, str]]]] = {
    "Q": [("8 inch", "10 inch"), ("6 inch", "8 inch")],
    "R": [("8 inch", "10 inch"), ("6 inch", "10 inch")],
}

# ✅ 反向映射：法兰尺寸 → 候选孔口列表
#   关键：H/G 双候选在 ("2 inch", "3 inch") 都合法
API526_FLANGE_TO_ORIFICES: Final[dict[tuple[str, str], list[PsvOrificeSize]]] = {
    ("1 inch",   "2 inch"):     ["D"],
    ("1.5 inch", "2.5 inch"):   ["E", "F"],
    ("1.5 inch", "3 inch"):     ["G"],              # 标准档 G（150#–900#）
    ("2 inch",   "3 inch"):     ["H", "G"],         # H + G 高压档双候选
    ("3 inch",   "4 inch"):     ["J", "K"],
    ("4 inch",   "6 inch"):     ["L", "M", "N"],
    ("6 inch",   "8 inch"):     ["P", "Q"],         # Q 变体
    ("6 inch",   "10 inch"):    ["R"],              # R 变体
    ("8 inch",   "10 inch"):    ["Q", "R", "T"],
}

# 高压档允许的法兰等级（API 526 Table 5：2G3 仅 1500#/2500#）
HIGH_PRESSURE_FLANGE_CLASSES: Final[frozenset[PsvFlangeClass]] = frozenset(
    {"1500#", "2500#"}
)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

# 提取英寸数字（"1.5 inch" → 1.5；"10 inch" → 10）
_SIZE_PATTERN = re.compile(r"^([\d.]+)\s*inch$")


def _parse_size_inch(size: str) -> float:
    """解析尺寸字符串为英寸数；解析失败 → 抛 ValueError。"""
    m = _SIZE_PATTERN.match(size.strip())
    if not m:
        raise ValueError(f"无效尺寸字符串: {size!r}（应形如 '1.5 inch'）")
    return float(m.group(1))


def size_lt(size_a: str, size_b: str) -> bool:
    """字符串尺寸严格小于（按英寸数）。"""
    return _parse_size_inch(size_a) < _parse_size_inch(size_b)


def size_le(size_a: str, size_b: str) -> bool:
    """字符串尺寸小于等于（按英寸数）。"""
    return _parse_size_inch(size_a) <= _parse_size_inch(size_b)


def is_high_pressure_flange(flange_class: PsvFlangeClass) -> bool:
    """1500#/2500# → True（API 526 Table 5：2G3 高压档）。"""
    return flange_class in HIGH_PRESSURE_FLANGE_CLASSES


def is_variant_configuration(
    inlet_size: str, outlet_size: str, orifice: PsvOrificeSize
) -> bool:
    """判断 (inlet, outlet) 是否为指定孔口的**非标准**厂商变体。

    variants 列表第一项通常与标准配置相同（用于自描述），
    非标准变体为 list[1:]。该函数仅在配置为非标准变体时返回 True。
    """
    variants = API526_ORIFICE_VARIANTS.get(orifice, [])
    if not variants:
        return False
    standard = API526_ORIFICE_TO_FLANGE.get(orifice)
    config = (inlet_size, outlet_size)
    if config == standard:
        return False
    return config in variants


# ---------------------------------------------------------------------------
# §3.3 get_candidate_orifices
# ---------------------------------------------------------------------------


def get_candidate_orifices(
    inlet_size: str,
    outlet_size: str,
    flange_class: PsvFlangeClass,
) -> list[PsvOrificeSize]:
    """根据入口/出口尺寸 + 法兰等级返回候选孔口。

    按 SPEC §3.3 逻辑：
    1. 反向映射查 (inlet, outlet) → 候选列表
    2. 对每个候选：
       - 若为 G 高压档配置（2G3）：1500#/2500# 允许；其他排除
       - 否则：所有法兰等级允许
    3. 返回过滤后列表（保持 API526_FLANGE_TO_ORIFICES 原序）

    Examples:
        >>> get_candidate_orifices("1.5 inch", "3 inch", "300#")
        ['G']
        >>> get_candidate_orifices("2 inch", "3 inch", "300#")
        ['H', 'G']  # H/G 双候选；G 仅为标准档（1.5×3）实际不存在，
                     # 因 G 在 2×3 是高压档配置
                     # 但反向映射 ("2 inch", "3 inch") 标了 H+G
                     # 需在过滤时排除非高压档 G
        >>> get_candidate_orifices("2 inch", "3 inch", "1500#")
        ['H', 'G']  # H 允许 + G 高压档允许
        >>> get_candidate_orifices("8 inch", "10 inch", "600#")
        ['Q', 'R', 'T']
    """
    candidates = API526_FLANGE_TO_ORIFICES.get((inlet_size, outlet_size), [])
    if not candidates:
        return []

    high_pressure = is_high_pressure_flange(flange_class)
    filtered: list[PsvOrificeSize] = []
    for orifice in candidates:
        hp_config = API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE.get(orifice)
        if hp_config is not None and hp_config == (inlet_size, outlet_size):
            # 该孔口在此 (inlet, outlet) 是高压档配置 → 仅高压法兰等级允许
            if high_pressure:
                filtered.append(orifice)
        else:
            # 标准档配置 → 所有法兰等级允许
            filtered.append(orifice)
    return filtered


# ---------------------------------------------------------------------------
# §3.4 法兰等级-孔口约束（Warning 占位）
# ---------------------------------------------------------------------------


# ⚠️ 待核验：API 526 Tables 2-15，逐孔口核验各压力等级
#    §8 gate #4 硬性：84 组合填充 + ≥20% 抽样核验
#    当前 None 矩阵 → 触发 validate_flange_orifice 时仅 Warning（不阻断）
FLANGE_CLASS_ORIFICE_LIMITS: Final[dict[PsvFlangeClass, list[PsvOrificeSize] | None]] = {
    "150#":  None,
    "300#":  None,
    "600#":  None,
    "900#":  None,
    "1500#": None,
    "2500#": None,
}


def check_flange_orifice_limit(
    flange_class: PsvFlangeClass,
    orifice: PsvOrificeSize,
    *,
    strict: bool = False,
) -> str | None:
    """法兰等级-孔口约束校验（Warning 占位）。

    Returns:
        None = 校验通过
        str = 警告消息（§3.4 行为：矩阵未填充时仅 Warning，矩阵已填充时阻塞）

    Args:
        strict: True 时矩阵未填充 → 抛 NotImplementedError（测试用）
    """
    allowed = FLANGE_CLASS_ORIFICE_LIMITS.get(flange_class)
    if allowed is None:
        if strict:
            raise NotImplementedError(
                f"法兰等级 {flange_class} 的孔口约束矩阵未填充（strict 模式）；"
                f"需按 API 526 Tables 2-15 逐孔口核验。"
            )
        return (
            f"法兰等级 {flange_class} 的孔口约束矩阵未填充（§8 gate #4 待 P5-3 工艺室核验），"
            f"已跳过校验；当前仅允许 {orifice} 通过。"
        )
    if orifice not in allowed:
        return (
            f"法兰等级 {flange_class} 不适用于孔口 {orifice}；"
            f"允许孔口：{allowed}"
        )
    return None


# ---------------------------------------------------------------------------
# §3.9 孔口-温度-分子量约束（API 520 §5.3.4）
# ---------------------------------------------------------------------------


# API 520 §5.3.4：Q/R/T 孔口在 T > 177°C 且 MW < 10 时，未经业主工程师批准不得使用
HIGH_TEMP_LIGHT_GAS_LIMIT_C: Final[float] = 177.0
HIGH_TEMP_LIGHT_GAS_MW_LIMIT: Final[float] = 10.0
HIGH_TEMP_RESTRICTED_ORIFICES: Final[frozenset[PsvOrificeSize]] = frozenset({"Q", "R", "T"})


def is_high_temp_light_gas_restricted(
    orifice: PsvOrificeSize,
    T_celsius: float | None,
    MW: float | None,
) -> bool:
    """判断 Q/R/T 孔口是否处于"高温低分子量"受限条件。

    Args:
        orifice: 孔口字母
        T_celsius: 流体温度 °C
        MW: 分子量 g/mol

    Returns:
        True = 受限（API 520 §5.3.4 需业主工程师批准）
    """
    if orifice not in HIGH_TEMP_RESTRICTED_ORIFICES:
        return False
    if T_celsius is None or MW is None:
        return False
    return T_celsius > HIGH_TEMP_LIGHT_GAS_LIMIT_C and MW < HIGH_TEMP_LIGHT_GAS_MW_LIMIT


__all__ = [
    "API526_ORIFICE_TO_FLANGE",
    "API526_ORIFICE_TO_FLANGE_HIGH_PRESSURE",
    "API526_ORIFICE_VARIANTS",
    "API526_FLANGE_TO_ORIFICES",
    "FLANGE_CLASS_ORIFICE_LIMITS",
    "HIGH_PRESSURE_FLANGE_CLASSES",
    "HIGH_TEMP_RESTRICTED_ORIFICES",
    "HIGH_TEMP_LIGHT_GAS_LIMIT_C",
    "HIGH_TEMP_LIGHT_GAS_MW_LIMIT",
    "API526_MIN_INLET",
    "get_candidate_orifices",
    "size_lt",
    "size_le",
    "is_high_pressure_flange",
    "is_variant_configuration",
    "check_flange_orifice_limit",
    "is_high_temp_light_gas_restricted",
]
