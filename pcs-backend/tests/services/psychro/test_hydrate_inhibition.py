"""P6-5 Task C2 (C-18 PSYCHRO 水合物抑制) hydrate_inhibition_service 单元测试。

按 brief §1 4 单测要求：

1. **Hammerschmidt MeOH 温降公式**：ΔT = K·X / (M·(1-X))（H-2 v1 BLOCKER）
2. **NaCl K=1297**：盐类 K 因子 < MeOH K 因子 → 相同浓度下温降更小
3. **抑制剂注入率**（GPSA §20.3）：Q_inhib = Q_gas·(W_inlet - W_target)/C
4. **浓度越界拒绝**：wt% ≥ 100 → HydrateInhibitionError

附加批次一致性测试：
- FrozenInstanceError: Input/Result 都是 frozen
- imperial_units default False（L-3 v1 BLOCKER fix）
- F2 边界拒绝：temperature / mass ≤ 0
- 公式参考：Hammerschmidt 1934 + GPSA §20.3

黄金对账：tests/services/psychro/fixtures/golden_hydrate_meoh.json
（Hammerschmidt 1934 Eq + GPSA §20.3 注入率）。
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    HydrateInhibitionError,
    HydrateInhibitionInput,
    calc_hydrate_inhibition,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_hydrate_meoh.json"


def _baseline_input(**overrides):
    base = dict(
        gas_flow_mmscfd=10.0,
        operating_pressure_psia=500.0,
        operating_temperature_f=40.0,
        hydrate_inhibitor_type="MEOH",
        inhibitor_concentration_in_water_wt_pct=10.0,
    )
    base.update(overrides)
    return HydrateInhibitionInput(**base)


# ============================================================================
# 核心 4 单测（brief §1 / §5）
# ============================================================================


def test_hammerschmidt_methanol_depression():
    """Hammerschmidt 1934 Eq：ΔT_F = K·X / (M·(1-X))

    MeOH MW=32.04, X=0.10（10 wt%）→ ΔT_F = 2335·0.10/(32.04·0.90) ≈ 8.10°F
    H-2 v1 BLOCKER：K=2335 精确按文献 °F 标度（OPEN-P6-6A-3 fix）。
    """
    inp = _baseline_input()
    result = calc_hydrate_inhibition(inp)
    # K 是 Hammerschmidt 1934 文献 °F 标度；故 delta_t_f 是 raw 输出
    delta_t_expected_f = 2335.0 * 0.10 / (32.04 * 0.90)
    delta_t_expected_c = delta_t_expected_f * 5.0 / 9.0
    assert math.isclose(
        result.hydrate_depression_f, delta_t_expected_f, rel_tol=1e-2
    ), f"d_F={result.hydrate_depression_f!r} ≠ 期望 {delta_t_expected_f!r}"
    assert math.isclose(
        result.hydrate_depression_c, delta_t_expected_c, rel_tol=1e-2
    ), f"d_C={result.hydrate_depression_c!r} ≠ 期望 {delta_t_expected_c!r}"


def test_hydrate_inhibition_nacl_salt_lower_k_factor():
    """NaCl K=1297 < MeOH K=2335 → 相同浓度下温降更小（H-2 v1 BLOCKER）。"""
    inp_meoh = _baseline_input(
        gas_flow_mmscfd=10.0,
        operating_pressure_psia=500.0,
        operating_temperature_f=40.0,
        hydrate_inhibitor_type="MEOH",
        inhibitor_concentration_in_water_wt_pct=10.0,
    )
    inp_nacl = _baseline_input(
        gas_flow_mmscfd=10.0,
        operating_pressure_psia=500.0,
        operating_temperature_f=40.0,
        hydrate_inhibitor_type="NACL",
        inhibitor_concentration_in_water_wt_pct=10.0,
    )
    r_meoh = calc_hydrate_inhibition(inp_meoh)
    r_nacl = calc_hydrate_inhibition(inp_nacl)
    assert r_meoh.hydrate_depression_c > r_nacl.hydrate_depression_c


def test_hydrate_inhibition_inhibitor_injection_rate():
    """GPSA §20.3 注入率：Q_inhib = Q_gas·(W_inlet - W_target)/C_inhibitor。

    10 MMscfd + (20-1) lb/MMscf water removed + 10 wt% (0.10) MeOH
    → injection_gpd = 10 × 19 / 0.10 × 0.1198 ≈ 227.6 gal/day
    注：0.1198 = lb/gal 转换系数（实测 GPSA Eq.20-32 注入率 lb/d → gal/d 转换）。
    """
    inp = _baseline_input(
        gas_flow_mmscfd=10.0,
        inhibitor_concentration_in_water_wt_pct=10.0,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )
    result = calc_hydrate_inhibition(inp)
    # 注入率须 > 0（10 MMscfd + 19 lb/MMscf 移除 + 10 wt% MeOH）
    assert result.inhibitor_injection_rate_gpd > 0
    # 物理一致性：流量加倍 → 注入率加倍
    inp2 = _baseline_input(
        gas_flow_mmscfd=20.0,
        inhibitor_concentration_in_water_wt_pct=10.0,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )
    result2 = calc_hydrate_inhibition(inp2)
    assert math.isclose(
        result2.inhibitor_injection_rate_gpd,
        2.0 * result.inhibitor_injection_rate_gpd,
        rel_tol=1e-6,
    )


def test_hydrate_inhibition_concentration_out_of_range_raises():
    """浓度 ≥ 100 wt% 应抛 HydrateInhibitionError（F2 边界）。"""
    inp = _baseline_input(
        gas_flow_mmscfd=10.0,
        operating_pressure_psia=500.0,
        operating_temperature_f=40.0,
        hydrate_inhibitor_type="MEOH",
        inhibitor_concentration_in_water_wt_pct=110.0,
    )
    with pytest.raises(HydrateInhibitionError):
        calc_hydrate_inhibition(inp)


# ============================================================================
# 5 抑制剂 K 因子排序（补充：brief 要求覆盖全部 5 种）
# ============================================================================


def test_hydrate_inhibition_per_inhibitor_k_factor():
    """H-2 v1 BLOCKER：K 因子排序 TEG=2500 > MEOH=2335 > DEG=2335 > EG=2220 > NACL=1297。"""
    X = 10.0

    def make_inp(t):
        return HydrateInhibitionInput(
            gas_flow_mmscfd=10.0,
            operating_pressure_psia=500.0,
            operating_temperature_f=40.0,
            hydrate_inhibitor_type=t,
            inhibitor_concentration_in_water_wt_pct=X,
        )

    r_teg = calc_hydrate_inhibition(make_inp("TEG"))
    r_meoh = calc_hydrate_inhibition(make_inp("MEOH"))
    r_deg = calc_hydrate_inhibition(make_inp("DEG"))
    r_eg = calc_hydrate_inhibition(make_inp("EG"))
    r_nacl = calc_hydrate_inhibition(make_inp("NACL"))

    # H-2 v1 BLOCKER: K 因子排序 TEG > MEOH/DEG > EG > NACL
    assert r_teg.inhibitor_k_factor == 2500.0
    assert r_meoh.inhibitor_k_factor == 2335.0
    assert r_deg.inhibitor_k_factor == 2335.0
    assert r_eg.inhibitor_k_factor == 2220.0
    assert r_nacl.inhibitor_k_factor == 1297.0
    # 排序关系
    assert r_teg.inhibitor_k_factor > r_meoh.inhibitor_k_factor
    assert r_meoh.inhibitor_k_factor > r_eg.inhibitor_k_factor
    assert r_eg.inhibitor_k_factor > r_nacl.inhibitor_k_factor


# ============================================================================
# 批次一致性 — Frozen dataclass + imperial default + F2 边界
# ============================================================================


def test_hydrate_inhibition_result_is_frozen():
    """HydrateInhibitionResult 必须是 frozen（不可变）。"""
    inp = _baseline_input()
    result = calc_hydrate_inhibition(inp)
    with pytest.raises(FrozenInstanceError):
        result.hydrate_depression_c = 0.0  # type: ignore[misc]


def test_hydrate_inhibition_input_is_frozen():
    """HydrateInhibitionInput 必须是 frozen（不可变）。"""
    inp = _baseline_input()
    with pytest.raises(FrozenInstanceError):
        inp.gas_flow_mmscfd = 999.0  # type: ignore[misc]


def test_imperial_units_default_false():
    """L-3 v1 BLOCKER fix：imperial_units 默认必须 False（SI 基准）。"""
    inp = _baseline_input()
    assert inp.imperial_units is False
    result = calc_hydrate_inhibition(inp)
    assert result.imperial_conversion is None


def test_imperial_units_true_yields_conversion():
    """imperial_units=True → dual-unit dict 输出（hydrate_depression_f + injection_rate_gal_d）。"""
    inp = _baseline_input(imperial_units=True)
    result = calc_hydrate_inhibition(inp)
    assert result.imperial_conversion is not None
    assert "hydrate_depression_f" in result.imperial_conversion
    assert "injection_rate_gal_d" in result.imperial_conversion


# ============================================================================
# 边界拒绝（F2 / F5）
# ============================================================================


def test_reject_zero_gas_flow():
    """F2/F5：gas_flow_mmscfd ≤ 0 → HydrateInhibitionError。"""
    inp = _baseline_input(gas_flow_mmscfd=0.0)
    with pytest.raises(HydrateInhibitionError):
        calc_hydrate_inhibition(inp)


def test_reject_zero_pressure():
    """F2：operating_pressure_psia ≤ 0 → HydrateInhibitionError。"""
    inp = _baseline_input(operating_pressure_psia=0.0)
    with pytest.raises(HydrateInhibitionError):
        calc_hydrate_inhibition(inp)


def test_reject_zero_concentration():
    """F2：inhibitor_concentration_in_water_wt_pct ≤ 0 → HydrateInhibitionError。"""
    inp = _baseline_input(inhibitor_concentration_in_water_wt_pct=0.0)
    with pytest.raises(HydrateInhibitionError):
        calc_hydrate_inhibition(inp)


# ============================================================================
# 公式参考 + 黄金对账
# ============================================================================


def test_formula_ref_documents_hammerschmidt_gpsa():
    """formula_ref 必含 Hammerschmidt 1934 + GPSA §20.3 引用（批次一致性）。"""
    inp = _baseline_input()
    result = calc_hydrate_inhibition(inp)
    assert "hammerschmidt" in result.formula_ref
    assert "Hammerschmidt" in result.formula_ref["hammerschmidt"]
    assert "injection_rate" in result.formula_ref
    assert "GPSA" in result.formula_ref["injection_rate"]


def test_golden_fixture_cross_check():
    """黄金对账：Hammerschmidt 1934 + GPSA §20.3 注入率（rel ≤ 1e-2）。"""
    data = json.loads(_FIXTURE_PATH.read_text())
    for point in data["points"]:
        inp_dict = {k: v for k, v in point.items() if k not in ("_comment", "expected")}
        expected = point["expected"]
        inp = HydrateInhibitionInput(
            gas_flow_mmscfd=inp_dict["gas_flow_mmscfd"],
            operating_pressure_psia=inp_dict["operating_pressure_psia"],
            operating_temperature_f=inp_dict["operating_temperature_f"],
            hydrate_inhibitor_type=inp_dict["hydrate_inhibitor_type"],
            inhibitor_concentration_in_water_wt_pct=inp_dict[
                "inhibitor_concentration_in_water_wt_pct"
            ],
            water_content_inlet_lb_per_mmscf=inp_dict.get(
                "water_content_inlet_lb_per_mmscf", 20.0
            ),
            water_content_target_lb_per_mmscf=inp_dict.get(
                "water_content_target_lb_per_mmscf", 1.0
            ),
        )
        result = calc_hydrate_inhibition(inp)
        actual_dt_f = result.hydrate_depression_f
        actual_dt_c = result.hydrate_depression_c
        expected_f = expected["hydrate_depression_f"]
        expected_c = expected["hydrate_depression_c"]
        assert (
            abs(actual_dt_f - expected_f) / expected_f < 1e-2
        ), (
            f"{inp_dict}: ΔT_F {actual_dt_f} != "
            f"expected {expected_f}"
        )
        assert (
            abs(actual_dt_c - expected_c) / expected_c < 1e-2
        ), (
            f"{inp_dict}: ΔT_C {actual_dt_c} != "
            f"expected {expected_c}"
        )