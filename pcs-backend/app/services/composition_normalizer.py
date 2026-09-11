"""P3.x SIM-31：composition_mass → composition_mole 归一化层 + 液相字段。

职责边界：
- **本模块**：mass→mole 纯数学换算 + 液相 JSONB 字段 pack/unpack
- **PropertyAutoCompleter（SIM-26）不变**：只接 composition_mole 做物性估算

换算公式（spec §1.2.4 + §5.2）：
    n_i = mass_i / MW_i
    x_i = n_i / Σ n_j

边界：
- MW 缺失 → `CompositionMassToMoleError`（message 含缺失 CAS）
- 负 mass fraction → ValueError
- MW=0 → ValueError（避免 ZeroDivisionError 不友好）
- 空输入 → 空 dict

液相 JSONB 字段（spec §1.2.3 stream_properties_json）：
- std_liq_density: kg/m³ @ 标准态
- liquid_mass_rate: kg/h
- liq_actual_m3hr: m³/h @ 工况
"""
from __future__ import annotations

from typing import Any


class CompositionMassToMoleError(ValueError):
    """mass→mole 转换错误（含 MW 缺失、负值、MW=0 等）。"""


# ---------------------------------------------------------------------------
# Mass → Mole 换算
# ---------------------------------------------------------------------------


def normalize_composition_mass_to_mole(
    composition_mass: dict[str, float],
    mw_by_component: dict[str, float],
) -> dict[str, float]:
    """mass fraction → mole fraction（归一化到 sum=1.0）。

    Args:
        composition_mass: {cas_or_libid: mass_fraction}
        mw_by_component: {cas_or_libid: molecular_weight}

    Returns:
        {cas_or_libid: mole_fraction}（sum=1.0，保留原 key）

    Raises:
        CompositionMassToMoleError: MW 缺失 / 负值 / MW=0
    """
    if not composition_mass:
        return {}

    # 校验负值
    for cas, frac in composition_mass.items():
        if frac < 0:
            raise CompositionMassToMoleError(
                f"composition_mass 中 {cas}={frac} 为负值"
            )

    # 校验 MW 缺失 / 零
    missing_mw = [cas for cas in composition_mass if mw_by_component.get(cas) is None]
    if missing_mw:
        raise CompositionMassToMoleError(
            f"以下组分的 molecular_weight (MW) 缺失，无法换算：{missing_mw}"
        )

    for cas, mw in mw_by_component.items():
        if cas in composition_mass and mw <= 0:
            raise CompositionMassToMoleError(
                f"组分 {cas} 的 MW={mw} ≤ 0，无法换算"
            )

    # 换算
    moles = {
        cas: frac / mw_by_component[cas] for cas, frac in composition_mass.items()
    }
    total = sum(moles.values())
    if total <= 0:
        raise CompositionMassToMoleError(
            "composition_mass 换算后总 mole ≤ 0，无法归一化"
        )
    return {cas: m / total for cas, m in moles.items()}


# ---------------------------------------------------------------------------
# 液相 JSONB 字段 pack/unpack
# ---------------------------------------------------------------------------

_LIQUID_JSONB_KEYS = ("std_liq_density", "liquid_mass_rate", "liq_actual_m3hr")


def pack_liquid_properties_json(
    raw: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """将 3 个液相字段打包进 stream_properties_json dict（保留已有键）。

    Returns:
        None → None；{} → {}；否则合并。
    """
    if raw is None:
        return None
    # 复制以避免 mutate 调用方
    merged: dict[str, Any] = dict(raw)
    return merged


def unpack_liquid_properties_json(
    stream_properties_json: dict[str, Any] | None,
) -> dict[str, float | None]:
    """从 stream_properties_json 提取 3 个液相字段；缺失键返回 None。

    Returns:
        {"std_liq_density": float|None, "liquid_mass_rate": float|None,
         "liq_actual_m3hr": float|None}
    """
    if not stream_properties_json:
        return {k: None for k in _LIQUID_JSONB_KEYS}
    return {
        k: stream_properties_json.get(k) for k in _LIQUID_JSONB_KEYS
    }


__all__ = [
    "CompositionMassToMoleError",
    "normalize_composition_mass_to_mole",
    "pack_liquid_properties_json",
    "unpack_liquid_properties_json",
    "_LIQUID_JSONB_KEYS",
]
