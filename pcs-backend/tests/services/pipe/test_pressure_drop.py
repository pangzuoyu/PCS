"""P4-2-3 PressureDropService 单元测试。

覆盖：
1. golden 单段直管：L=10m, D=0.05m, ρ=1000, μ=1e-3, Q=0.001 m³/s, ε=4.5e-5
   → 手算 Re, f, dp_friction
2. fittings K 值：elbow_90 + tee_branch + valve_gate → dp_fittings 累加
3. 层流兜底：Re<2300 → f=64/Re
4. 边界：P1=0 → raise；D=0 → raise；Q=0 → dp=0；Re 越界 → raise
5. 路由标记：dp_total/P1 < 10% → need_two_phase=False；≥10% → need_two_phase=True
6. 显式 K 覆盖：fitting.K=1.5 → 覆盖默认
7. 两相入口短路：fluid_phase='TWO_PHASE' → need_two_phase=True
8. fittings K 表加载：JSON 校验每个 type 都有默认 K

Golden 溯源：
- Darcy-Weisbach + Colebrook-White（Crane TP-410 / Perry's 8th ed. §6）
- fittings K 值表（Crane TP-410 / Idelchik 'Handbook of Hydraulic Resistance' 第 4 版）
- ρ/μ 默认值按 fluid_phase 查 sizing_service 已有默认物性表（避免重复造表）
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.pipe.pressure_drop_service import (
    Fitting,
    PipeSegment,
    PressureDropInputError,
    PressureDropRangeError,
    PressureDropResult,
    calc_pressure_drop,
    load_fittings_k_default,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载
# ---------------------------------------------------------------------------


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_pressure_drop.json"
_K_TABLE_PATH = Path(__file__).parent / "fixtures" / "fittings_k_default.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
K_DEFAULT = json.loads(_K_TABLE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 辅助构造
# ---------------------------------------------------------------------------


def _make_straight_segment(**overrides) -> PipeSegment:
    """构造标准直管段（用于 golden / 单测）。"""
    defaults = {
        "L_m": 10.0,
        "D_m": 0.05,
        "roughness_m": 4.5e-5,
        "fluid_density": 1000.0,
        "fluid_viscosity": 1.0e-3,
        "flow_rate_m3s": 0.001,
        "fittings": [],
    }
    defaults.update(overrides)
    return PipeSegment(**defaults)


# ---------------------------------------------------------------------------
# 1) golden 单段直管
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_golden_single_straight_water():
    """golden：L=10m, D=0.05m, ρ=1000, μ=1e-3, Q=0.001, ε=4.5e-5 → dp_friction≈687.46 Pa。"""
    golden = GOLDEN["single_straight_water"]
    seg = _make_straight_segment(
        L_m=golden["L_m"],
        D_m=golden["D_m"],
        roughness_m=golden["roughness_m"],
        fluid_density=golden["rho"],
        fluid_viscosity=golden["mu"],
        flow_rate_m3s=golden["Q_m3s"],
    )
    P1 = 200_000.0  # 200 kPa，保证 ΔP/P₁ ≈ 0.34% << 10%
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert isinstance(res, PressureDropResult)
    assert math.isclose(
        res.dp_friction_pa, golden["dp_friction_pa"], abs_tol=golden["tolerance"]
    )
    assert math.isclose(res.reynolds, golden["reynolds"], abs_tol=1.0)
    assert math.isclose(
        res.friction_factor, golden["friction_factor"], abs_tol=1e-4
    )
    assert res.flow_regime == "TURBULENT"
    assert res.confidence == "HIGH"  # Re≈25465 > 10000, TURBULENT
    assert res.check_result == "PASS"
    assert res.need_two_phase is False


# ---------------------------------------------------------------------------
# 2) fittings K 值累加
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_fittings_k_accumulates():
    """fittings K 值累加：dp_fittings = sum(K_i) × ρv²/2。"""
    seg = _make_straight_segment(
        fittings=[
            Fitting(type="elbow_90"),       # K=0.9
            Fitting(type="tee_branch"),    # K=1.0
            Fitting(type="valve_gate"),    # K=0.15
        ]
    )
    P1 = 200_000.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")

    # 直管 dp + fittings dp
    # v = Q/A = 0.001 / (π × 0.05² / 4) = 0.509296 m/s
    rho = 1000.0
    v_expected = 0.001 / (math.pi * 0.05 ** 2 / 4)
    K_sum = (
        K_DEFAULT["elbow_90"]["k"]
        + K_DEFAULT["tee_branch"]["k"]
        + K_DEFAULT["valve_gate"]["k"]
    )
    dp_fittings_expected = K_sum * rho * v_expected ** 2 / 2.0

    assert math.isclose(
        res.dp_fittings_pa, dp_fittings_expected, rel_tol=1e-9
    )
    assert math.isclose(
        res.dp_total_pa, res.dp_friction_pa + res.dp_fittings_pa, rel_tol=1e-12
    )
    # dp_total_kpa_per_100m 换算正确：总压降 / 1000 × 100 / L_m → kPa/100m
    expected_kpa_100m = res.dp_total_pa / 1000.0 * 100.0 / seg.L_m
    assert math.isclose(res.dp_total_kpa_per_100m, expected_kpa_100m, rel_tol=1e-12)


def test_calc_pressure_drop_explicit_K_overrides_default():
    """显式 K 覆盖默认：fitting.K=1.5 → 使用 1.5 而非默认 0.9。"""
    seg_default = _make_straight_segment(
        fittings=[Fitting(type="elbow_90")]  # K=0.9
    )
    seg_explicit = _make_straight_segment(
        fittings=[Fitting(type="elbow_90", K=1.5)]  # 显式覆盖
    )
    P1 = 200_000.0
    res_default = calc_pressure_drop(seg_default, P1_pa=P1, fluid_phase="LIQUID")
    res_explicit = calc_pressure_drop(seg_explicit, P1_pa=P1, fluid_phase="LIQUID")

    # 直管摩阻相同
    assert math.isclose(res_default.dp_friction_pa, res_explicit.dp_friction_pa, rel_tol=1e-12)
    # fittings dp 之差 = (1.5 - 0.9) × ρv²/2
    v = 0.001 / (math.pi * 0.05 ** 2 / 4)
    delta = (1.5 - 0.9) * 1000.0 * v ** 2 / 2.0
    assert math.isclose(
        res_explicit.dp_fittings_pa - res_default.dp_fittings_pa, delta, rel_tol=1e-9
    )


# ---------------------------------------------------------------------------
# 3) 层流兜底
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_laminar_uses_64_over_Re():
    """层流（Re<2000）：f = 64/Re；confidence=LOW（Crane K 表 Re 区间外）。"""
    # 极低流速：Q=1e-5 m³/s, D=0.05 → v≈0.00509 → Re≈254（层流）
    seg = _make_straight_segment(
        flow_rate_m3s=1.0e-5,
    )
    P1 = 200_000.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.flow_regime == "LAMINAR"
    assert res.reynolds < 2000.0
    f_expected = 64.0 / res.reynolds
    assert math.isclose(res.friction_factor, f_expected, rel_tol=1e-9)
    # P4-2-5: LAMINAR → confidence=LOW（Crane K 表 Re 区间外）
    assert res.confidence == "LOW"
    assert res.check_result == "PASS"
    assert res.check_result_reason is None


# ---------------------------------------------------------------------------
# 4) 边界
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_P1_zero_raises():
    """P1=0 → raise PressureDropInputError（压降分母退化）。"""
    seg = _make_straight_segment()
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=0.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_P1_negative_raises():
    """P1<0 → raise PressureDropInputError。"""
    seg = _make_straight_segment()
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=-100.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_D_zero_raises():
    """D=0 → raise PressureDropInputError（管径退化）。"""
    seg = _make_straight_segment(D_m=0.0)
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_Q_zero_returns_zero_dp():
    """Q=0 → v=0 → dp_friction=0, dp_fittings=0, dp_total=0；不 raise。"""
    seg = _make_straight_segment(flow_rate_m3s=0.0)
    P1 = 200_000.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.dp_friction_pa == 0.0
    assert res.dp_fittings_pa == 0.0
    assert res.dp_total_pa == 0.0
    assert res.reynolds == 0.0
    assert res.flow_regime == "LAMINAR"


def test_calc_pressure_drop_Q_negative_raises():
    """Q<0 → raise PressureDropInputError。"""
    seg = _make_straight_segment(flow_rate_m3s=-0.001)
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_rho_zero_raises():
    """ρ≤0 → raise PressureDropInputError。"""
    seg = _make_straight_segment(fluid_density=0.0)
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_mu_zero_raises():
    """μ≤0 → raise PressureDropInputError。"""
    seg = _make_straight_segment(fluid_viscosity=0.0)
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")


def test_calc_pressure_drop_Re_too_low_raises():
    """Re < 100 → raise PressureDropRangeError。"""
    # 极小 Q 但不为 0：Q=1e-8 → v≈5e-5 → Re≈2.5（<100 但 >0）
    seg = _make_straight_segment(flow_rate_m3s=1.0e-8)
    P1 = 200_000.0
    with pytest.raises(PressureDropRangeError):
        calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")


def test_calc_pressure_drop_Re_too_high_raises():
    """Re > 1e8 → raise PressureDropRangeError。"""
    # 极大 Q：Q=10 → v≈5093 m/s → Re≈2.5e8（>1e8）
    seg = _make_straight_segment(flow_rate_m3s=10.0)
    P1 = 200_000.0
    with pytest.raises(PressureDropRangeError):
        calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")


# ---------------------------------------------------------------------------
# 5) 路由标记（ΔP/P₁ 阈值）
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_incompressible_when_ratio_below_10_percent():
    """ΔP/P₁ < 10% → need_two_phase=False（不可压缩近似）。"""
    seg = _make_straight_segment()
    # P1 极大 → ratio 远低于 10%
    P1 = 10_000_000.0  # 10 MPa
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.dp_ratio < 0.1
    assert res.need_two_phase is False


def test_calc_pressure_drop_routes_to_two_phase_when_ratio_above_10_percent():
    """ΔP/P₁ ≥ 10% → need_two_phase=True（路由至 P4-2-4）。"""
    # 单段压降 ≈ 687 Pa；要 P1 足够小使 ratio ≥ 10%
    # ratio = dp_total / P1 ≥ 0.10 → P1 ≤ 687 / 0.10 = 6870 Pa
    seg = _make_straight_segment()  # dp_friction ≈ 687 Pa + fittings 0 = 687
    P1 = 5000.0  # 5 kPa：ratio ≈ 13.7% → 路由
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.dp_ratio >= 0.1
    assert res.need_two_phase is True


def test_calc_pressure_drop_routing_boundary_at_10_percent():
    """ratio 恰在 10% 边界：≥ 10% 触发路由。"""
    seg = _make_straight_segment()
    # dp_friction ≈ 687.46；ratio 恰 0.10 → P1 = 687.46 / 0.10 ≈ 6875
    # 取略小确保 ratio 略大于 10%
    P1 = 6800.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.need_two_phase is True


# ---------------------------------------------------------------------------
# 6) 两相入口短路
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_two_phase_input_short_circuits():
    """fluid_phase='TWO_PHASE' → 短路计算，need_two_phase=True（由 P4-2-4 接管）。"""
    seg = _make_straight_segment()
    res = calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="TWO_PHASE")
    assert res.need_two_phase is True


# ---------------------------------------------------------------------------
# 7) fittings K 表加载 + 完整覆盖
# ---------------------------------------------------------------------------


def test_load_fittings_k_default_returns_all_types():
    """load_fittings_k_default 返回全部 10 个 type 的 K 值 + v2 元数据。"""
    k_table = load_fittings_k_default()
    expected_types = [
        "elbow_90", "elbow_45", "tee_branch", "tee_through",
        "valve_gate", "valve_ball", "reducer", "expander",
        "entrance", "exit",
    ]
    for t in expected_types:
        assert t in k_table
        meta = k_table[t]
        # v2 schema: FittingKMeta 含 k + reynolds_applicable + k_factor_confidence + source
        assert hasattr(meta, "k")
        assert isinstance(meta.k, float)
        assert hasattr(meta, "reynolds_applicable")
        assert isinstance(meta.reynolds_applicable, str)
        assert hasattr(meta, "k_factor_confidence")
        assert meta.k_factor_confidence in ("HIGH", "MEDIUM", "LOW")
        assert hasattr(meta, "source")
        assert isinstance(meta.source, str)


# ---------------------------------------------------------------------------
# 8) P4-2-5：3 态流场 + confidence + check_result
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_transition_regime_warning():
    """过渡区（2000≤Re≤4000）：f=Colebrook；check_result=WARNING(reason="TRANSITION_REGIME")。

    Re≈3000 设计：D=0.05, Q=6e-4 → v=0.3056 → Re=15278 → 实际太高。重新选：
    油 μ=0.05 Pa·s, D=0.05, Q=2.0e-3 → v=1.019 → Re=ρvD/μ=1000×1.019×0.05/0.05=1019 (层流)
    Re≈3000：D=0.05, ρ=1000, μ=0.017, Q=1.018e-2 → v=5.19 → Re=15265（太高）
    Re≈3000：D=0.05, ρ=1000, μ=0.085, Q=5.1e-3 → v=2.6 → Re=1529（层流）
    用油 μ=0.05，D=0.05, Q=4.8e-3 → v=2.44 → Re=2444（接近过渡区下限）
    为 Re≈3000：D=0.05, ρ=1000, μ=0.04, Q=3.84e-3 → v=1.957 → Re=2446
    实际 D=0.05 ρ=1000 v=Q/(π×0.05²/4)=Q/0.001963
    目标 Re=3000：v = Re·μ/(ρD) = 3000×0.04/(1000×0.05) = 2.4 m/s → Q=2.4×0.001963=4.71e-3
    """
    seg = _make_straight_segment(
        fluid_viscosity=0.04,  # 油
        flow_rate_m3s=4.71e-3,  # → v=2.4, Re=3000
    )
    P1 = 200_000.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert 2000.0 <= res.reynolds <= 4000.0, f"reynolds={res.reynolds}"
    assert res.flow_regime == "TRANSITION"
    assert res.check_result == "WARNING"
    assert res.check_result_reason == "TRANSITION_REGIME"
    # P4-2-5: TRANSITION → confidence=MEDIUM
    assert res.confidence == "MEDIUM"


def test_calc_pressure_drop_turbulent_medium_confidence():
    """湍流 Re ∈ (4000, 10000]：confidence=MEDIUM（K 表部分适用）。"""
    # Re=5000：D=0.05, ρ=1000, μ=0.02, Q=？→ v=Re·μ/(ρD)=5000×0.02/50=2.0 m/s
    # Q=v·A=2.0×0.001963=3.93e-3
    seg = _make_straight_segment(
        fluid_viscosity=0.02,
        flow_rate_m3s=3.93e-3,
    )
    P1 = 200_000.0
    res = calc_pressure_drop(seg, P1_pa=P1, fluid_phase="LIQUID")
    assert res.reynolds > 4000.0
    assert res.reynolds <= 10000.0
    assert res.flow_regime == "TURBULENT"
    assert res.check_result == "PASS"
    assert res.confidence == "MEDIUM"  # Re ≤ 10000 → MEDIUM


def test_calc_pressure_drop_get_fitting_k_signature():
    """get_fitting_k 签名：传 diameter + reynolds；当前实现忽略 Re 返回固定 K。"""
    from app.services.pipe.pressure_drop_service import get_fitting_k

    k_low, conf = get_fitting_k("elbow_90", diameter_m=0.05, reynolds=100.0)
    k_high, conf2 = get_fitting_k("elbow_90", diameter_m=0.05, reynolds=1.0e7)
    # 当前实现：固定 K（与 Re 无关；P5+ 改 Hooper 2-K 时再分桶）
    assert k_low == k_high
    assert conf == conf2
    assert conf == "HIGH"


def test_calc_pressure_drop_get_fitting_k_invalid_type_raises():
    """get_fitting_k 未知 type → raise。"""
    from app.services.pipe.pressure_drop_service import get_fitting_k

    with pytest.raises(PressureDropInputError):
        get_fitting_k("elbow_unknown", diameter_m=0.05, reynolds=1000.0)  # type: ignore[arg-type]


def test_calc_pressure_drop_get_fitting_k_invalid_diameter_raises():
    """get_fitting_k D≤0 → raise。"""
    from app.services.pipe.pressure_drop_service import get_fitting_k

    with pytest.raises(PressureDropInputError):
        get_fitting_k("elbow_90", diameter_m=0.0, reynolds=1000.0)


def test_calc_pressure_drop_get_fitting_k_negative_reynolds_raises():
    """get_fitting_k Re<0 → raise。"""
    from app.services.pipe.pressure_drop_service import get_fitting_k

    with pytest.raises(PressureDropInputError):
        get_fitting_k("elbow_90", diameter_m=0.05, reynolds=-1.0)


def test_fittings_k_default_values_match_crane_tp_410():
    """固化 K 值与 Crane TP-410 / Idelchik 常用值匹配（容差 0.01）。"""
    # 见 fixtures/fittings_k_default.json _source
    assert math.isclose(K_DEFAULT["elbow_90"]["k"], 0.9, abs_tol=0.01)
    assert math.isclose(K_DEFAULT["elbow_45"]["k"], 0.4, abs_tol=0.01)
    assert math.isclose(K_DEFAULT["tee_branch"]["k"], 1.0, abs_tol=0.01)
    assert math.isclose(K_DEFAULT["tee_through"]["k"], 0.2, abs_tol=0.01)
    assert math.isclose(K_DEFAULT["valve_gate"]["k"], 0.15, abs_tol=0.01)
    assert math.isclose(K_DEFAULT["valve_ball"]["k"], 0.05, abs_tol=0.01)


# ---------------------------------------------------------------------------
# 8) fluid_phase 仅用于路由判断 / 不影响流体物性
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fluid_phase",
    ["LIQUID", "GAS", "STEAM"],
)
def test_calc_pressure_drop_fluid_phase_does_not_affect_fluid_properties(fluid_phase):
    """fluid_phase 只用于路由判断；流体物性完全由 seg.fluid_density/viscosity 决定。"""
    seg = _make_straight_segment()  # 水物性
    res_liquid = calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")
    res_other = calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase=fluid_phase)
    # 流相不是 TWO_PHASE 时，物性完全由 seg 决定 → dp 一致
    assert math.isclose(res_liquid.dp_friction_pa, res_other.dp_friction_pa, rel_tol=1e-12)
    assert math.isclose(res_liquid.friction_factor, res_other.friction_factor, rel_tol=1e-12)


def test_calc_pressure_drop_unknown_fluid_phase_raises():
    """未知 fluid_phase → raise PressureDropInputError（业务错误）。"""
    seg = _make_straight_segment()
    with pytest.raises(PressureDropInputError):
        calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="PLASMA")


# ---------------------------------------------------------------------------
# 9) Darcy-Weisbach 公式直接验证
# ---------------------------------------------------------------------------


def test_calc_pressure_drop_formula_darcy_weisbach():
    """dp_friction = f × (L/D) × (ρ × v²/2) 直接验证。"""
    seg = _make_straight_segment()
    res = calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")
    v = seg.flow_rate_m3s / (math.pi * seg.D_m ** 2 / 4.0)
    dp_expected = res.friction_factor * (seg.L_m / seg.D_m) * (seg.fluid_density * v ** 2 / 2.0)
    assert math.isclose(res.dp_friction_pa, dp_expected, rel_tol=1e-9)


def test_calc_pressure_drop_formula_fittings():
    """dp_fittings = (ΣK_i) × ρ × v²/2 直接验证。"""
    seg = _make_straight_segment(
        fittings=[
            Fitting(type="elbow_90"),       # K=0.9
            Fitting(type="valve_ball"),     # K=0.05
        ]
    )
    res = calc_pressure_drop(seg, P1_pa=200_000.0, fluid_phase="LIQUID")
    v = seg.flow_rate_m3s / (math.pi * seg.D_m ** 2 / 4.0)
    K_sum = K_DEFAULT["elbow_90"]["k"] + K_DEFAULT["valve_ball"]["k"]
    dp_expected = K_sum * seg.fluid_density * v ** 2 / 2.0
    assert math.isclose(res.dp_fittings_pa, dp_expected, rel_tol=1e-9)