"""SUP-P5-PSV-002 V1.14 §4.3 Kb 4 阶段策略 + 合成 _KB_DATA seed。

按 SPEC V1.14 §4.3：

策略（按优先级）：
1. SPRING_LOADED + bp_pct <= 0 → "none" / 1.0（API 520 标准定义）
2. valve_brand 指定 + 单厂商在 _KB_DATA → 厂商专属曲线
3. valve_brand 是 mixed 形式（"mfr1+mfr2"）且所有 mfr 在 _KB_DATA → 平均
4. fallback：保守回退（api520_fig30 / en4126）
   - 默认 api520_fig30；PILOT_OPERATED 专用 en4126（P5 拦截）

线性插值：相邻 overpressure_pct 之间用线性插值

数据（SYNTHETIC_TEST_DATA）：
- 3 厂商 × 3 overpressure 曲线点（10%/16%/21%）
- 工艺工程师后续替换（P5-3 数据收集）

设计要点：
- valve_brand 接受 "LESER" 或 "manufacturer:LESER"（自动 normalize）
- mixed 形式："LESER+Consolidated"（无 manufacturer: 前缀）
- 阶段 4 默认 api520_fig30；PILOT_OPERATED 走 en4126（P5 拦截）

不做：
- 不区分 BALANCED_BELLOWS / SPRING_LOADED 曲线族（合成数据共用一组；P6+ 按厂商细分）
- 不实现 Kb < 1.0 时的 backpressure-combined 综合判定（§3.5 P6+）
"""
from __future__ import annotations

from typing import Final

from app.services.psv.valve_selection_types import PsvKbSource

# ---------------------------------------------------------------------------
# §4.3 Kb 合成数据
# ---------------------------------------------------------------------------

# SYNTHETIC_TEST_DATA: 工艺工程师后续替换（P5-3 数据收集）
# 结构：manufacturer -> {overpressure_pct: Kb_factor}
_KB_DATA: Final[dict[str, dict[float, float]]] = {
    "manufacturer:LESER": {
        10.0: 1.00,
        16.0: 0.95,
        21.0: 0.90,
    },
    "manufacturer:Consolidated": {
        10.0: 1.00,
        16.0: 0.96,
        21.0: 0.92,
    },
    "manufacturer:Anderson_Greenwood": {
        10.0: 1.00,
        16.0: 0.94,
        21.0: 0.88,
    },
}

# 保守回退曲线（API 520 Fig.30 / EN 4126 共用）
_CONSERVATIVE_KB_FALLBACK: Final[dict[float, float]] = {
    10.0: 1.00,
    16.0: 0.93,
    21.0: 0.87,
}

# 全部 overpressure 离散点（插值边界）
_ALL_OVERPRESSURES: Final[tuple[float, ...]] = (10.0, 16.0, 21.0)


# ---------------------------------------------------------------------------
# §4.3 内部工具
# ---------------------------------------------------------------------------


def _interpolate_kb(points: dict[float, float], overpressure_pct: float) -> float:
    """线性插值 Kb 曲线。

    Args:
        points: {overpressure_pct: Kb_factor} 曲线
        overpressure_pct: 当前超压百分比

    Returns:
        插值后的 Kb_factor

    Notes:
        - overpressure_pct <= min(points) → min(points)
        - overpressure_pct >= max(points) → max(points)
        - 区间内：两点线性插值
    """
    if not points:
        raise ValueError("插值点集不能为空")
    sorted_ops = sorted(points.keys())
    if overpressure_pct <= sorted_ops[0]:
        return points[sorted_ops[0]]
    if overpressure_pct >= sorted_ops[-1]:
        return points[sorted_ops[-1]]
    for i in range(len(sorted_ops) - 1):
        x0, x1 = sorted_ops[i], sorted_ops[i + 1]
        if x0 <= overpressure_pct <= x1:
            y0, y1 = points[x0], points[x1]
            return y0 + (y1 - y0) * (overpressure_pct - x0) / (x1 - x0)
    raise ValueError(f"unreachable: overpressure_pct={overpressure_pct}")


def _normalize_brand(brand: str) -> str:
    """Normalize brand: 'manufacturer:LESER' 或 'LESER' → 'manufacturer:LESER'。"""
    if brand.startswith("manufacturer:"):
        return brand
    return f"manufacturer:{brand}"


def _parse_mixed_brand(brand: str) -> list[str] | None:
    """检查 brand 是否为 mixed 形式（"mfr1+mfr2"，无 manufacturer: 前缀）。

    Returns:
        list of normalized single-brand keys（含"manufacturer:"前缀）；不是 mixed → None
    """
    if "+" not in brand:
        return None
    parts = [p.strip() for p in brand.split("+")]
    if any(not p for p in parts):
        return None
    # 不允许 mixed 内部含 "manufacturer:" 前缀（约定）
    if any(":" in p for p in parts):
        return None
    return [f"manufacturer:{p}" for p in parts]


def _kb_for_single_brand(brand: str, overpressure_pct: float) -> float | None:
    """单厂商 Kb 查询；brand 不在数据 → 返回 None（触发回退）。"""
    full_key = _normalize_brand(brand)
    if full_key not in _KB_DATA:
        return None
    return _interpolate_kb(_KB_DATA[full_key], overpressure_pct)


def _kb_for_mixed_brand(
    brand_keys: list[str], overpressure_pct: float
) -> float | None:
    """mixed Kb 查询：所有 brand 都在 _KB_DATA → 算术平均；任一不在 → 返回 None。

    保守：用算术平均（SPEC §4.3 P3-3）
    """
    values: list[float] = []
    for brand in brand_keys:
        if brand not in _KB_DATA:
            return None
        values.append(_interpolate_kb(_KB_DATA[brand], overpressure_pct))
    return sum(values) / len(values)


def _kb_conservative(overpressure_pct: float) -> float:
    """保守回退曲线（api520_fig30 / en4126 共用）。"""
    return _interpolate_kb(_CONSERVATIVE_KB_FALLBACK, overpressure_pct)


# ---------------------------------------------------------------------------
# §4.3 lookup_kb_with_priority 4 阶段策略
# ---------------------------------------------------------------------------


def lookup_kb_with_priority(
    bp_pct: float,
    overpressure_pct: float,
    valve_type: str,
    valve_brand: str | None = None,
) -> tuple[float, PsvKbSource]:
    """Kb 4 阶段策略（§4.3 + §8 gate #10）。

    Args:
        bp_pct: 背压百分比（built-up 或 superimposed；通常 bp_pct = total - superimposed）
        overpressure_pct: 超压百分比（10/16/21；前端 V1.14 §5.2 PsvOverpressureSelect）
        valve_type: 阀体型式（PsvValveType；SPRING_LOADED/BALANCED_BELLOWS/PILOT/...）
        valve_brand: 阀体品牌（自由字符串；前端 PsvValveBrand 透传；
                       mixed 形式"LESER+Consolidated"；可含或不含"manufacturer:"前缀）

    Returns:
        (Kb_factor, kb_source)

    Strategy:
        1. SPRING_LOADED + bp_pct <= 0 → ("none", 1.0)
        2. valve_brand 指定 + 在 _KB_DATA → (valve_brand, kb)
        3. valve_brand 是 mixed 形式 → ("mixed:mfr1+mfr2", avg_kb)
        4. fallback：保守回退（api520_fig30 / en4126）
           - 默认 api520_fig30；PILOT_OPERATED 专用 en4126（P5 拦截）
    """
    # 策略 1：标准定义（API 520：弹簧式零背压 = Kb=1.0）
    if valve_type == "SPRING_LOADED" and bp_pct <= 0:
        return (1.0, "none")

    # PILOT_OPERATED 专用 en4126（P5 拦截；不论 brand 一律走 en4126 保守回退）
    if valve_type == "PILOT_OPERATED":
        return (_kb_conservative(overpressure_pct), "en4126")

    # 策略 2/3：brand 查表（mixed 优先 → 否则单 brand）
    if valve_brand:
        # mixed 形式优先
        mixed_keys = _parse_mixed_brand(valve_brand)
        if mixed_keys is not None:
            kb = _kb_for_mixed_brand(mixed_keys, overpressure_pct)
            if kb is not None:
                return (kb, f"mixed:{valve_brand}")
        # 单 brand（normalize 后查）
        kb = _kb_for_single_brand(valve_brand, overpressure_pct)
        if kb is not None:
            return (kb, _normalize_brand(valve_brand))  # type: ignore[return-value]

    # 策略 4：保守回退
    return (_kb_conservative(overpressure_pct), "api520_fig30")


__all__ = ["lookup_kb_with_priority"]