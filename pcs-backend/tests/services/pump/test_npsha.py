"""P4-4-2 NPSHa 计算 单元测试（纯函数，不落库）。

覆盖：
1. 基础 NPSHa 计算：(Ps - Pv) / (ρg) - h_loss
2. margin > 0 → PASS，margin_m / margin_pct 正确
3. margin < 0 → check_result=FAIL (reason=NEGATIVE_MARGIN)
4. 精度护栏：吸入侧任一段 confidence=LOW → 强制 WARNING (SUCTION_LOW_RE_UNCERTAINTY)
5. 精度护栏：吸入侧任一段 flow_regime=TRANSITION → 强制 WARNING
6. MEDIUM 可 PASS：metadata confidence=MEDIUM，check_result=PASS
7. HIGH 全 PASS：confidence=HIGH，check_result=PASS
8. 边界：Ps ≤ Pv / ρ ≤ 0 / h_loss 负数 → raise
9. 两相段参与：suction 含两相段 → 不报错，正常计算

公式来源：ANSI/HI 9.6.6-2016（NPSH available）
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.pump.npsha_service import (
    NPSHaInput,
    NPSHaInputError,
    calc_npsha,
)


def _u() -> uuid.UUID:
    return uuid.uuid4()


def _make_turbulent_chain():
    """构造 1 段 TURBULENT+HIGH confidence 的吸入管段（D=0.05, L=10, 水）。"""
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    seg = PipeSegmentInput(
        fluid_phase="LIQUID",
        mass_flow_kg_s=1.0,
        density_kg_m3=1000.0,
        viscosity_pa_s=1e-3,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.6e-5,
        length_m=10.0,
        fittings=[],
    )
    return PipeChainInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="SUC-1",
        segments=[seg],
        inlet_pressure_pa=200000.0,
        inlet_temperature_K=300.0,
    )


def _make_laminar_chain():
    """构造 1 段 LAMINAR+LOW confidence 的吸入管段（Re ≈ 1000）。"""
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    seg = PipeSegmentInput(
        fluid_phase="LIQUID",
        mass_flow_kg_s=0.0785,  # Re ≈ 1000 → LOW
        density_kg_m3=1000.0,
        viscosity_pa_s=1e-3,
        pipe_diameter_m=0.1,
        pipe_roughness_m=4.5e-5,
        length_m=10.0,
        fittings=[],
    )
    return PipeChainInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="SUC-LAM",
        segments=[seg],
        inlet_pressure_pa=200000.0,
        inlet_temperature_K=300.0,
    )


def _make_transition_chain():
    """构造 1 段 TRANSITION（2000 ≤ Re ≤ 4000）的吸入管段。"""
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    # 目标 Re ≈ 3000：v = Re*μ/(ρ*D) = 3000*1e-3/(1000*0.05) = 0.06 m/s
    # Q = v*A = 0.06 * π*0.05²/4 ≈ 1.178e-4 m³/s
    # ṁ = ρ*Q ≈ 0.1178 kg/s
    seg = PipeSegmentInput(
        fluid_phase="LIQUID",
        mass_flow_kg_s=0.1178,
        density_kg_m3=1000.0,
        viscosity_pa_s=1e-3,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        length_m=10.0,
        fittings=[],
    )
    return PipeChainInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="SUC-TR",
        segments=[seg],
        inlet_pressure_pa=200000.0,
        inlet_temperature_K=300.0,
    )


def _make_two_phase_chain():
    """构造 1 段 TWO_PHASE 的吸入管段。"""
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    seg = PipeSegmentInput(
        fluid_phase="TWO_PHASE",
        mass_flow_kg_s=0.0,  # 两相段忽略
        density_kg_m3=0.0,   # 两相段忽略
        viscosity_pa_s=0.0,  # 两相段忽略
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.5e-5,
        length_m=10.0,
        surface_tension_n_m=0.072,
        liquid_density_kg_m3=1000.0,
        liquid_viscosity_pa_s=1e-3,
        gas_density_kg_m3=1.0,
        gas_viscosity_pa_s=1e-5,
        liquid_mass_flow_kg_s=1.0,
        gas_mass_flow_kg_s=0.01,
        fittings=[],
    )
    return PipeChainInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="SUC-TP",
        segments=[seg],
        inlet_pressure_pa=200000.0,
        inlet_temperature_K=300.0,
    )


_FIXTURES = Path(__file__).parent / "fixtures"


def _load_golden():
    with (_FIXTURES / "golden_npsha.json").open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. 基础 NPSHa 计算
# ---------------------------------------------------------------------------


def test_basic_npsha_within_tolerance():
    """Golden：20°C 水、D=0.05、L=10、ṁ=1 kg/s → NPSHa ≈ 10.00 m（容差 5%）。"""
    g = _load_golden()["cold_water_centrifugal_pump"]
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=g["system_pressure_pa"],
        vapor_pressure_pa=g["vapor_pressure_pa"],
        fluid_density_kg_m3=g["fluid_density_kg_m3"],
        fluid_viscosity_pa_s=g["fluid_viscosity_pa_s"],
        suction_pipe_chain=_make_turbulent_chain(),
        elevation_change_m=g["elevation_change_m"],
    )
    r = calc_npsha(inp)
    # 期望 ≈ 10.00 m
    assert r.npsha_m == pytest.approx(g["expected_npsha_m"], rel=g["tolerance"])
    assert r.h_friction_m > 0.0
    assert r.h_fittings_m >= 0.0
    assert r.h_elevation_m == 0.0
    assert r.check_result in ("PASS", "WARNING", "FAIL")


# ---------------------------------------------------------------------------
# 2. margin 计算
# ---------------------------------------------------------------------------


def test_margin_positive_when_npsha_exceeds_npshr():
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_turbulent_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp, npshr_m=2.0)
    assert r.margin_m is not None
    assert r.margin_pct is not None
    assert r.margin_m > 0.0
    assert r.margin_pct == pytest.approx(r.margin_m / 2.0 * 100.0, rel=1e-9)


# ---------------------------------------------------------------------------
# 3. margin < 0 → FAIL
# ---------------------------------------------------------------------------


def test_negative_margin_returns_fail():
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=101325.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_turbulent_chain(),
        elevation_change_m=8.0,  # 抬升 8 m，NPSHa 大幅下降
    )
    r = calc_npsha(inp, npshr_m=20.0)  # NPSHr 远大于 NPSHa
    assert r.margin_m is not None
    assert r.margin_m < 0.0
    assert r.check_result == "FAIL"
    assert r.check_result_reason == "NEGATIVE_MARGIN"


# ---------------------------------------------------------------------------
# 4. 精度护栏 LOW → WARNING
# ---------------------------------------------------------------------------


def test_low_confidence_segment_forces_warning():
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_laminar_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp, npshr_m=1.0)  # 即使 margin > 0，仍应 WARNING
    assert r.suction_confidence == "LOW"
    assert r.check_result == "WARNING"
    assert r.check_result_reason == "SUCTION_LOW_RE_UNCERTAINTY"


# ---------------------------------------------------------------------------
# 5. 精度护栏 TRANSITION → WARNING
# ---------------------------------------------------------------------------


def test_transition_segment_forces_warning():
    """TRANSITION 流态 → 强制 WARNING（即使 margin > 0 也禁止 PASS）。"""
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_transition_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp, npshr_m=1.0)
    assert r.flow_regime_summary.get("TRANSITION", 0) >= 1
    assert r.check_result == "WARNING"
    assert r.check_result_reason == "SUCTION_LOW_RE_UNCERTAINTY"


# ---------------------------------------------------------------------------
# 6. MEDIUM 可 PASS
# ---------------------------------------------------------------------------


def test_medium_confidence_passes_with_metadata():
    """MEDIUM confidence → check_result=PASS，metadata confidence=MEDIUM。"""
    # 两相段 chain 整体 confidence = MEDIUM
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_two_phase_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp, npshr_m=1.0)
    assert r.suction_confidence == "MEDIUM"
    # margin > 0 且非 LOW/TRANSITION → PASS
    assert r.check_result == "PASS"


# ---------------------------------------------------------------------------
# 7. HIGH 全 PASS
# ---------------------------------------------------------------------------


def test_all_turbulent_high_passes():
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_turbulent_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp, npshr_m=1.0)
    assert r.suction_confidence == "HIGH"
    assert r.flow_regime_summary.get("TURBULENT", 0) >= 1
    assert r.check_result == "PASS"
    assert r.check_result_reason is None


# ---------------------------------------------------------------------------
# 8. 边界：Ps ≤ Pv / ρ ≤ 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "system_pressure_pa,vapor_pressure_pa,density",
    [
        (2338.0, 2338.0, 1000.0),   # Ps == Pv
        (1000.0, 2338.0, 1000.0),   # Ps < Pv
        (200000.0, 2338.0, 0.0),    # rho = 0
        (200000.0, 2338.0, -1000.0),  # rho < 0
    ],
)
def test_invalid_inputs_raise(system_pressure_pa, vapor_pressure_pa, density):
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=system_pressure_pa,
        vapor_pressure_pa=vapor_pressure_pa,
        fluid_density_kg_m3=density,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_turbulent_chain(),
        elevation_change_m=0.0,
    )
    with pytest.raises(NPSHaInputError):
        calc_npsha(inp)


# ---------------------------------------------------------------------------
# 9. 两相段参与
# ---------------------------------------------------------------------------


def test_two_phase_chain_uses_two_phase_dp():
    """suction 含两相段 → calc_chain 内部路由，不报错。"""
    inp = NPSHaInput(
        project_id=_u(),
        workspace_id=_u(),
        source_stream_id=_u(),
        tag_number="P-1001",
        system_pressure_pa=200000.0,
        vapor_pressure_pa=2338.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1e-3,
        suction_pipe_chain=_make_two_phase_chain(),
        elevation_change_m=0.0,
    )
    r = calc_npsha(inp)
    assert r.npsha_m > 0.0
    assert r.suction_confidence == "MEDIUM"  # 两相段默认 MEDIUM
