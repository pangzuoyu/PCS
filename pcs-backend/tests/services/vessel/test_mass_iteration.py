"""P6-4 T3 C-12 mass_iteration_loop 测试（V1.2 接口冻结）。

按 SPEC §3.4.4 C-12 + WS-CA-PR-010 §5.3：
- 6 测试（variable='D' +4, variable='L' +2）
- Newton + bisection 双路径
- 不收敛抛 MassIterationNotConvergedError
- D7 接口冻结（ADR-0040）
"""
from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, fields

import pytest

from app.services.vessel.vessel_service import (
    MassIterationInput,
    MassIterationNotConvergedError,
    MassIterationResult,
    VesselInputError,
    mass_iteration_loop,
)

# ============================================================================
# 1. VERTICAL + variable='D' 收敛到已知解
# ============================================================================


def test_mass_iteration_vertical_D_converges():
    """VERTICAL + variable='D'：H=D 假设；D=2/L=5/2:1 ELLIPSE/target=5774 → D≈2.0001。"""
    # mass(D=2, L=5)=5774.04; target=5774 略低 → D 略 < 2.0
    inp = MassIterationInput(
        target_mass_kg=5774.0,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.2,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=1.5,
        initial_L_m=5.0,
        variable="D",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert math.isclose(result.final_variable_m, 2.0, rel_tol=1e-3)
    assert math.isclose(result.final_mass_kg, 5774.0, rel_tol=1e-6)
    assert abs(result.residual_kg) < 1e-3
    # formula_ref 标注 method
    assert result.formula_ref["method"] == "Newton"


# ============================================================================
# 2. HORIZONTAL + variable='L'（variable='L' +1）
# ============================================================================


def test_mass_iteration_horizontal_L_converges():
    """HORIZONTAL + variable='L'：H=D/2 假设；D=2/target=2387/2:1 ELLIPSE → L=5.07。"""
    inp = MassIterationInput(
        target_mass_kg=2387.0,
        rho_L_kg_m3=900.0,
        rho_V_kg_m3=2.0,
        vessel_shape="HORIZONTAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=2.0,
        initial_L_m=4.0,
        variable="L",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert math.isclose(result.final_variable_m, 5.07, rel_tol=1e-2)
    assert abs(result.residual_kg) < 1e-3
    assert result.formula_ref["variable"] == "L"


# ============================================================================
# 3. SPHERICAL + variable='D'（球缺公式 + Newton 收敛）
# ============================================================================


def test_mass_iteration_spherical_D_converges():
    """SPHERICAL + variable='D'：球缺公式 π·H²·(R-H/3), H=D；target=4000/ρ=850 → D≈2.08。"""
    inp = MassIterationInput(
        target_mass_kg=4000.0,
        rho_L_kg_m3=850.0,
        rho_V_kg_m3=1.5,
        vessel_shape="SPHERICAL",
        head_type="FLAT",
        initial_D_m=1.5,
        initial_L_m=0.0,
        variable="D",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert math.isclose(result.final_variable_m, 2.0791, rel_tol=1e-3)
    assert math.isclose(result.final_mass_kg, 4000.0, rel_tol=1e-6)
    assert result.formula_ref["vessel_shape"] == "SPHERICAL"


# ============================================================================
# 4. VERTICAL + variable='L'（variable='L' +2）
# ============================================================================


def test_mass_iteration_vertical_L_converges():
    """VERTICAL + variable='L'：H=D 假设；D=2/target=5774.04（mass at L=5）→ L=5.0。"""
    # mass(D=2, L=5, 2:1 ELLIPSE, ρ_L=1000, ρ_V=1.2) = 5774.04 kg
    inp = MassIterationInput(
        target_mass_kg=5774.04,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.2,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=2.0,
        initial_L_m=3.0,
        variable="L",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert math.isclose(result.final_variable_m, 5.0, rel_tol=1e-3)
    assert math.isclose(result.final_mass_kg, 5774.04, rel_tol=1e-3)
    assert result.formula_ref["variable"] == "L"


def test_mass_iteration_hemi_D_converges():
    """HEMISPHERICAL + VERTICAL + variable='D'：验证 HEMI 封头分支。"""
    # D=2, L=5, HEMI: V_partial at H=D=2:
    #   b=1, z_bottom=1 → V_head_bottom = π·1·(1 - 1/3) = 2π/3 ≈ 2.094
    #   L_liq_bottom=1, z_top = max(0, 2-5-1)=0
    #   L_liq_cyl = min(1, 5)-0 = 1
    #   V_cyl = π·1·1 = π ≈ 3.142
    #   V_partial = 2π/3 + π = 5π/3 ≈ 5.236
    #   V_total = π·1·5 + 2·π·8/12 = 5π + 4π/3 = 19π/3 ≈ 19.897
    # mass = 1000·5.236 + 1·(19.897 - 5.236) = 5236 + 14.661 = 5250.7
    target_mass = 1000.0 * (5 * math.pi / 3) + 1.0 * (
        19 * math.pi / 3 - 5 * math.pi / 3
    )
    inp = MassIterationInput(
        target_mass_kg=target_mass,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.0,
        vessel_shape="VERTICAL",
        head_type="HEMISPHERICAL",
        initial_D_m=1.5,
        initial_L_m=5.0,
        variable="D",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert math.isclose(result.final_variable_m, 2.0, rel_tol=1e-3)


# ============================================================================
# 5. 不收敛场景：max_iter 触发 MassIterationNotConvergedError
# ============================================================================


def test_mass_iteration_no_converge_raises():
    """target=1e-12 kg + max_iter=10：bisection 也找不到 bracket → 抛 NotConvergedError。"""
    inp = MassIterationInput(
        target_mass_kg=1e-12,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.0,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=1.0,
        initial_L_m=3.0,
        variable="D",
        mass_model="OPERATING",
    )
    with pytest.raises(MassIterationNotConvergedError) as exc_info:
        mass_iteration_loop(inp, tol=1e-6, max_iter=10)
    assert "未收敛" in str(exc_info.value)
    # 异常 code 必填
    assert exc_info.value.code == "MASS_ITERATION_NOT_CONVERGED"
    assert exc_info.value.status == 422


# ============================================================================
# 6. 输入校验
# ============================================================================


def test_mass_iteration_invalid_target_raises():
    """target_mass_kg ≤ 0 应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        mass_iteration_loop(
            MassIterationInput(
                target_mass_kg=0.0,
                rho_L_kg_m3=1000.0,
                rho_V_kg_m3=1.0,
                vessel_shape="VERTICAL",
                head_type="2:1_ELLIPTICAL",
                initial_D_m=1.0,
                initial_L_m=3.0,
            )
        )


def test_mass_iteration_rho_L_less_than_V_raises():
    """ρ_L < ρ_V 倒置应抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        mass_iteration_loop(
            MassIterationInput(
                target_mass_kg=1000.0,
                rho_L_kg_m3=1.0,
                rho_V_kg_m3=1000.0,
                vessel_shape="VERTICAL",
                head_type="2:1_ELLIPTICAL",
                initial_D_m=1.0,
                initial_L_m=3.0,
            )
        )


def test_mass_iteration_EMPTY_not_implemented():
    """EMPTY mass_model 本批不实现，应抛 VesselInputError。"""
    inp = MassIterationInput(
        target_mass_kg=1000.0,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.0,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=1.0,
        initial_L_m=3.0,
        mass_model="EMPTY",
    )
    with pytest.raises(VesselInputError, match="EMPTY"):
        mass_iteration_loop(inp)


# ============================================================================
# 7. 数据类契约（frozen dataclass，D7 接口冻结）
# ============================================================================


def test_mass_iteration_dataclasses_frozen():
    """MassIterationInput / MassIterationResult 字段冻结校验。"""
    in_fields = {f.name for f in fields(MassIterationInput)}
    expected_in = {
        "target_mass_kg",
        "rho_L_kg_m3",
        "rho_V_kg_m3",
        "vessel_shape",
        "head_type",
        "initial_D_m",
        "initial_L_m",
        "variable",
        "mass_model",
    }
    assert in_fields == expected_in

    out_fields = {f.name for f in fields(MassIterationResult)}
    expected_out = {
        "converged",
        "iterations",
        "final_variable_m",
        "final_mass_kg",
        "residual_kg",
        "formula_ref",
    }
    assert out_fields == expected_out

    inp = MassIterationInput(
        target_mass_kg=1000.0,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.0,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
    )
    with pytest.raises(FrozenInstanceError):
        inp.target_mass_kg = 2000.0  # type: ignore[misc]