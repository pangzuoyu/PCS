"""P6-6A-7 SPEC §3.7.2 C-19 排污孔板 sizing inverse problem tests.

5 单元测试 + 1 反向验证（forward vs inverse 一致性）+ 1 边界用例。
"""

import json
from pathlib import Path

import pytest

from app.services.restriction.drain_orifice_service import (
    DrainOrificeInput,
    DrainOrificeInputError,
    DrainOrificeSizeInput,
    DrainOrificeSizingNotConvergedError,
    calc_drain_orifice,
    calc_drain_orifice_size,
)

_FIX_DIR = Path(__file__).parent / "fixtures"


def _load_golden():
    return json.loads((_FIX_DIR / "golden_drain_orifice_size_pr023.json").read_text())


def _build_input() -> DrainOrificeSizeInput:
    return DrainOrificeSizeInput(**_load_golden()["service_inputs"])


# ─────────────────────────────────────────────────────────────
# Test 1: 黄金 fixture 对账 XLS PR-023
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_golden_xls_pr023_orifice_diameter_match():
    """XLS PR-023 输入 + 求解 → d ≈ 15.204 mm（Ruling 7 0.2% 容差内）。"""
    inp = _build_input()
    result = calc_drain_orifice_size(inp)

    expected = _load_golden()["expected"]
    assert result.converged, "应收敛"
    assert result.orifice_diameter_m == pytest.approx(
        expected["orifice_diameter_m"], rel=2e-3
    )
    assert result.beta_ratio == pytest.approx(expected["beta_ratio"], rel=2e-3)
    assert result.is_choked is True
    assert result.iterations <= expected["iterations_max"]


# ─────────────────────────────────────────────────────────────
# Test 2: 反向验证 — forward vs inverse 一致性
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_forward_inverse_consistency():
    """sizing 求解的 d 传给 forward → m_max 应等于 W（自洽验证）。"""
    inp = _build_input()
    size_result = calc_drain_orifice_size(inp)

    # 把 sizing 求解的 d 喂给 forward
    fwd_inp = DrainOrificeInput(
        orifice_diameter_m=size_result.orifice_diameter_m,
        beta_ratio=size_result.beta_ratio,
        inlet_pressure_kpa=inp.inlet_pressure_kpa,
        outlet_pressure_kpa=inp.outlet_pressure_kpa,
        fluid_density_kg_m3=_compute_rho(inp),
        mass_flow_kg_s=inp.relief_flow_kg_s,
        drain_type="CONTINUOUS",
        discharge_coefficient=inp.discharge_coefficient,
        expansion_factor=size_result.y_cr_sqrt,
    )
    fwd_result = calc_drain_orifice(fwd_inp)

    # forward 算出的 m_max 应约等于 W（self-consistency）
    assert fwd_result.mass_flow_capacity_kg_s == pytest.approx(
        inp.relief_flow_kg_s, rel=2e-2
    )
    assert fwd_result.is_capacity_ok is True


# ─────────────────────────────────────────────────────────────
# Test 3: 非阻塞流抛错
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_non_choked_flow_raises():
    """P2/P1 > r_c 时 sizing 不适用 → 422 DrainOrificeInputError。"""
    inp = _build_input()
    # 把 P2 提到 P1 附近，破坏阻塞
    non_choked_inp = DrainOrificeSizeInput(
        **{
            **inp.__dict__,
            "outlet_pressure_kpa": inp.inlet_pressure_kpa * 0.95,  # p_ratio=0.95 > r_c(1.18)≈0.56
        }
    )
    with pytest.raises(DrainOrificeInputError, match="非阻塞流"):
        calc_drain_orifice_size(non_choked_inp)


# ─────────────────────────────────────────────────────────────
# Test 4: 输入校验 — relief_flow ≤ 0 抛错
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_zero_relief_flow_raises():
    inp = _build_input()
    with pytest.raises(DrainOrificeInputError, match="relief_flow_kg_s"):
        zero_inp = DrainOrificeSizeInput(**{**inp.__dict__, "relief_flow_kg_s": 0.0})
        calc_drain_orifice_size(zero_inp)


# ─────────────────────────────────────────────────────────────
# Test 5: Cd 越界抛错
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_cd_out_of_range_raises():
    inp = _build_input()
    with pytest.raises(DrainOrificeInputError, match="Cd"):
        bad_cd_inp = DrainOrificeSizeInput(
            **{**inp.__dict__, "discharge_coefficient": 1.5}
        )
        calc_drain_orifice_size(bad_cd_inp)


# ─────────────────────────────────────────────────────────────
# Test 6: 不收敛抛错（max_iter 触发）
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_not_converged_raises():
    """max_iter=1 + 病态初值 → 不收敛抛 422。"""
    inp = _build_input()
    impatient_inp = DrainOrificeSizeInput(
        **{**inp.__dict__, "max_iter": 1, "initial_d_m": inp.pipe_diameter_m * 0.99}
    )
    with pytest.raises(DrainOrificeSizingNotConvergedError, match="d 迭代"):
        calc_drain_orifice_size(impatient_inp)


# ─────────────────────────────────────────────────────────────
# helper
# ─────────────────────────────────────────────────────────────
def _compute_rho(inp: DrainOrificeSizeInput) -> float:
    """与 service 内的 ρ 公式一致（理想气体）。"""
    R = 8.314462618
    return (
        inp.molecular_weight_kg_kmol
        * inp.inlet_pressure_kpa
        * 1000.0
        / (inp.compressibility_z * R * 1e3 * inp.temperature_k)
    )
