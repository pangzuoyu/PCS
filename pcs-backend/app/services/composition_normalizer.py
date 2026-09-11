"""P3.x SIM-31: composition_mass → composition_mole 归一化层。

职责边界：
- **本模块**：mass→mole 纯数学换算
- **PropertyAutoCompleter（SIM-26）不变**：只接 composition_mole 做物性估算
- 液相 3 字段（std_liq_density/liquid_mass_rate/liq_actual_m3hr）在 SIM-33 已从
  JSONB 迁 ORM（liquid_std_density/liquid_mass_rate/liquid_actual_m3hr）；
  pack/unpack 函数已删除。

换算公式（spec §1.2.4 + §5.2）：
    n_i = mass_i / MW_i
    x_i = n_i / Σ n_j

边界：
- MW 缺失 → `CompositionMassToMoleError`（message 含缺失 CAS）
- 负 mass fraction → ValueError
- MW=0 → ValueError（避免 ZeroDivisionError 不友好）
- 空输入 → 空 dict
"""
from __future__ import annotations


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


__all__ = [
    "CompositionMassToMoleError",
    "normalize_composition_mass_to_mole",
]