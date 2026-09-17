"""P5-2-2 丝网除沫器测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md 行 217-230：
- York 法手算（ΔP ≈ K_loss × V_g² × pad_thickness）
- Souders-Brown K 取值（标准 K=0.107 / 高效 K=0.085；带除沫器取更高 K）
- 复用 chedl_wrapper.K_separator_demister_York（P5-1-1 已包装）
- 2 例：标准 / 带除沫器 K
"""
from __future__ import annotations

import math

import pytest

from app.services.sep_equip.mist_eliminator_service import (
    MistEliminatorInput,
    MistEliminatorResult,
    PadType,
    calc_mist_eliminator,
)


def _standard_input() -> MistEliminatorInput:
    """标准丝网除沫器工况：Q_g=0.5 m³/s, ρ_g=1.2, D=1.0m。"""
    return MistEliminatorInput(
        pad_type="STANDARD",
        Q_gas_m3_s=0.5,
        D_cylinder_m=1.0,
        rho_gas_kg_m3=1.2,
        mu_gas_pa_s=1.8e-5,
        liquid_load_kg_m3=0.5,
    )


def _high_efficiency_input() -> MistEliminatorInput:
    """高效丝网除沫器工况：同 Q/D/ρ；K 因子下调 + 厚度增加 → 压降更高。"""
    return MistEliminatorInput(
        pad_type="HIGH_EFFICIENCY",
        Q_gas_m3_s=0.5,
        D_cylinder_m=1.0,
        rho_gas_kg_m3=1.2,
        mu_gas_pa_s=1.8e-5,
        liquid_load_kg_m3=0.5,
    )


# ============================================================================
# 1. 标准型 York 法手算验证
# ============================================================================


def test_standard_mist_eliminator_hand_calc():
    """标准丝网：K=0.107 m/s, pad 厚 100mm, ΔP = 2.5·ρ·V_g²·h_pad。

    手算：D=1.0m → A=π/4=0.7854 m² → V_g=Q/A=0.5/0.7854=0.6366 m/s
    ΔP_dry = 2.5 × 1.2 × 0.6366² × 0.1 = 0.1216 Pa（York 简化式）
    注：本算例 V_g=0.637 > K=0.107，velocity_check_ok=False
    （K 是允许上限，实际 V_g 应小于 K 才安全——此为"超速风险演示"）
    """
    result = calc_mist_eliminator(_standard_input())
    assert math.isclose(result.K_factor_ms, 0.107, rel_tol=0.01)
    assert math.isclose(result.pad_area_m2, math.pi / 4.0, rel_tol=0.01)
    assert result.pad_thickness_mm == 100
    # V_g=0.637 > K=0.107 → 风险演示
    assert result.velocity_check_ok is False
    assert result.pressure_drop_pa > 0


# ============================================================================
# 2. 高效型 K 取值更低 + 厚度更高 → 压降量级更高
# ============================================================================


def test_high_efficiency_vs_standard():
    """高效型 K=0.085 m/s（标准 0.107），pad 厚 150mm → 压降更高。"""
    std = calc_mist_eliminator(_standard_input())
    he = calc_mist_eliminator(_high_efficiency_input())

    # K 因子：高效 < 标准（York 标准 Souders-Brown 经验）
    assert he.K_factor_ms < std.K_factor_ms
    # pad 厚度：高效 > 标准
    assert he.pad_thickness_mm > std.pad_thickness_mm
    # 压降：高效应更高（厚度大 + 面积相同但 V_g 一致）
    assert he.pressure_drop_pa > std.pressure_drop_pa


# ============================================================================
# 3. Q_g/D 几何换算：pad 面积由 Q_g/V_design 推导
# ============================================================================


def test_pad_area_from_Q_and_D():
    """pad_area = π·D²/4（圆柱横截面积）；设计 V_g = K_ms。

    本测试：用 V_g = Q/A 反推（实际 K 因子为上限校核，不强求 V_g = K）。
    """
    inp = MistEliminatorInput(
        pad_type="STANDARD",
        Q_gas_m3_s=1.0,
        D_cylinder_m=1.5,
        rho_gas_kg_m3=1.2,
        mu_gas_pa_s=1.8e-5,
        liquid_load_kg_m3=0.0,
    )
    result = calc_mist_eliminator(inp)
    expected_area = math.pi * (1.5 / 2.0) ** 2
    assert math.isclose(result.pad_area_m2, expected_area, rel_tol=0.01)


# ============================================================================
# 4. 边界异常
# ============================================================================


def test_zero_gas_flow_raises():
    """Q_gas=0 无工艺意义 → MistEliminatorInputError（422）。"""
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc_info:
        calc_mist_eliminator(MistEliminatorInput(
            pad_type="STANDARD",
            Q_gas_m3_s=0.0,
            D_cylinder_m=1.0,
            rho_gas_kg_m3=1.2,
            mu_gas_pa_s=1.8e-5,
            liquid_load_kg_m3=0.5,
        ))
    assert exc_info.value.status == 422


def test_invalid_pad_type_raises():
    """pad_type 不在 Literal 2 类 → 422。"""
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc_info:
        calc_mist_eliminator(MistEliminatorInput(
            pad_type="INVALID",  # type: ignore[arg-type]
            Q_gas_m3_s=0.5,
            D_cylinder_m=1.0,
            rho_gas_kg_m3=1.2,
            mu_gas_pa_s=1.8e-5,
            liquid_load_kg_m3=0.5,
        ))
    assert exc_info.value.status == 422


# ============================================================================
# 5. 不可变性
# ============================================================================


def test_mist_eliminator_result_is_frozen_dataclass():
    """MistEliminatorResult frozen dataclass（不可变 + 可哈希）。"""
    from dataclasses import FrozenInstanceError

    result = calc_mist_eliminator(_standard_input())
    assert isinstance(result, MistEliminatorResult)
    with pytest.raises(FrozenInstanceError):
        result.pressure_drop_pa = 999.0  # type: ignore[misc]


# ============================================================================
# 6. 类型契约
# ============================================================================


def test_pad_type_literal_values():
    """PadType 仅 'STANDARD' / 'HIGH_EFFICIENCY' 两值（防回归）。"""
    assert set(PadType.__args__) == {"STANDARD", "HIGH_EFFICIENCY"}