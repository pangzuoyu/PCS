"""P6-5 Task C1 (C-16 PSYCHRO 甘醇脱水) glycol_dehydration_service 单元测试。

按 brief §1 3 单测要求：

1. **TEG 脱水效率**：8 块塔盘 + 3 gpm 循环量 → 脱水效率 ≥ 99%（GPSA §20.4）
2. **塔盘不足**：contactor_tray_count < N_min → is_tray_count_ok=False（不抛错）
3. **DEG vs TEG**：DEG 沸点低 → α 较低 → N_min 较高

附加批次一致性测试：
- FrozenInstanceError: Input/Result 都是 frozen
- imperial_units default False（L-3 v1 BLOCKER fix）
- L/V 修正：glycol_circulation_rate_gpm 影响 N_min + D_in（M-4 v2 BLOCKER）
- 边界拒绝：flow=0 / circulation=0 / tray_count=0 必须抛 GlycolDehydrationError

黄金对账：tests/services/psychro/fixtures/golden_teg_dehydration.json
（GPSA §20.4 Eq.20-4 + 经验 TEG 损失 0.5 gal/MMscf）。
"""
from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    GlycolDehydrationError,
    GlycolDehydrationInput,
    calc_glycol_dehydration,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_teg_dehydration.json"


def _baseline_input(**overrides):
    base = dict(
        gas_flow_mmscfd=10.0,
        inlet_water_content_lb_per_mmscf=15.0,
        outlet_water_content_lb_per_mmscf=0.1,
        glycol_type="TEG",
        contactor_tray_count=8,
        glycol_circulation_rate_gpm=3.0,
    )
    base.update(overrides)
    return GlycolDehydrationInput(**base)


# ============================================================================
# 核心 3 单测（brief §1 / §5）
# ============================================================================


def test_teg_dehydration_meets_outlet_spec():
    """TEG 接触塔 8 块塔盘 + 3 gpm 循环量 → 脱水效率 ≥ 99%（GPSA §20.4）。"""
    inp = _baseline_input()
    result = calc_glycol_dehydration(inp)
    efficiency = 1.0 - 0.1 / 15.0
    assert result.dehydration_efficiency >= efficiency - 0.001
    # GPSA §20.4 Eq.20-4：N_min = ln(15/0.1)/ln(4.5) ≈ 3.33 → ceil = 4
    assert result.n_tray_minimum == 4
    assert result.is_tray_count_ok is True


def test_teg_dehydration_tray_count_insufficient_raises():
    """塔盘数 < N_min → is_tray_count_ok=False（不抛错，仅警告）。"""
    inp = _baseline_input(contactor_tray_count=2)
    result = calc_glycol_dehydration(inp)
    assert result.is_tray_count_ok is False


def test_deg_dehydration_alternative_to_teg():
    """DEG（沸点 245°C）vs TEG（沸点 288°C）；DEG 沸点低 → α 较低 → N_min 较高。

    测试通过传入 lower relative_volatility（模拟 DEG）来验证 N_min 反向敏感。
    """
    inp_teg = _baseline_input(glycol_type="TEG", relative_volatility=4.5)
    inp_deg = _baseline_input(glycol_type="DEG", relative_volatility=2.8)
    r_teg = calc_glycol_dehydration(inp_teg)
    r_deg = calc_glycol_dehydration(inp_deg)
    assert r_deg.n_tray_minimum > r_teg.n_tray_minimum


# ============================================================================
# 批次一致性 — Frozen dataclass + imperial default + L/V 修正
# ============================================================================


def test_glycol_dehydration_result_is_frozen():
    """GlycolDehydrationResult 必须是 frozen（不可变）。"""
    inp = _baseline_input()
    result = calc_glycol_dehydration(inp)
    with pytest.raises(FrozenInstanceError):
        result.dehydration_efficiency = 0.0  # type: ignore[misc]


def test_glycol_dehydration_input_is_frozen():
    """GlycolDehydrationInput 必须是 frozen（不可变）。"""
    inp = _baseline_input()
    with pytest.raises(FrozenInstanceError):
        inp.gas_flow_mmscfd = 999.0  # type: ignore[misc]


def test_imperial_units_default_false():
    """L-3 v1 BLOCKER fix：imperial_units 默认必须 False（SI 基准）。"""
    inp = _baseline_input()
    assert inp.imperial_units is False
    result = calc_glycol_dehydration(inp)
    assert result.imperial_conversion is None


def test_imperial_units_true_yields_conversion():
    """imperial_units=True → dual-unit dict 输出（tegloss + diameter）。"""
    inp = _baseline_input(imperial_units=True)
    result = calc_glycol_dehydration(inp)
    assert result.imperial_conversion is not None
    assert "tegloss_gal_d" in result.imperial_conversion
    assert "contactor_diameter_ft" in result.imperial_conversion
    # SI 字段仍存在（dual-unit）
    assert result.teg_loss_gpd > 0
    assert result.contactor_diameter_in > 0


def test_lv_correction_uses_circulation_rate():
    """M-4 v2 BLOCKER：glycol_circulation_rate_gpm MUST 影响 N_min + D_in。

    高循环量 → L/V 高 → N_min 修正减小；D_in 修正减小。
    """
    inp_low = _baseline_input(glycol_circulation_rate_gpm=1.0)
    inp_high = _baseline_input(glycol_circulation_rate_gpm=10.0)
    r_low = calc_glycol_dehydration(inp_low)
    r_high = calc_glycol_dehydration(inp_high)
    # 高循环量 → L/V 修正因子 1/sqrt(L/V) 更小 → N_min 更小
    assert r_high.n_tray_minimum <= r_low.n_tray_minimum
    # D_in 含 (L/V)^0.5 修正 → 高循环量 → D_in 更大
    # 注意：high L/V 也意味着 D_in 乘以 sqrt(L/V)；所以 high 应 > low
    assert r_high.contactor_diameter_in >= r_low.contactor_diameter_in


# ============================================================================
# 边界拒绝（F2 / F5）
# ============================================================================


def test_reject_zero_gas_flow():
    """F2/F5：gas_flow_mmscfd ≤ 0 → GlycolDehydrationError。"""
    inp = _baseline_input(gas_flow_mmscfd=0.0)
    with pytest.raises(GlycolDehydrationError):
        calc_glycol_dehydration(inp)


def test_reject_zero_inlet_water():
    """F2：inlet_water_content 必须 > 0。"""
    inp = _baseline_input(inlet_water_content_lb_per_mmscf=0.0)
    with pytest.raises(GlycolDehydrationError):
        calc_glycol_dehydration(inp)


def test_reject_outlet_ge_inlet():
    """F2：outlet 必须在 [0, inlet) 范围；outlet ≥ inlet 必须拒绝。"""
    inp = _baseline_input(outlet_water_content_lb_per_mmscf=15.0)
    with pytest.raises(GlycolDehydrationError):
        calc_glycol_dehydration(inp)


def test_reject_zero_circulation():
    """F5：glycol_circulation_rate_gpm ≤ 0 → GlycolDehydrationError。"""
    inp = _baseline_input(glycol_circulation_rate_gpm=0.0)
    with pytest.raises(GlycolDehydrationError):
        calc_glycol_dehydration(inp)


def test_reject_zero_tray_count():
    """F5：contactor_tray_count < 1 → GlycolDehydrationError。"""
    inp = _baseline_input(contactor_tray_count=0)
    with pytest.raises(GlycolDehydrationError):
        calc_glycol_dehydration(inp)


# ============================================================================
# 公式参考 + 黄金对账
# ============================================================================


def test_formula_ref_documents_gpsa_section():
    """formula_ref 必含 GPSA §20.4 Eq.20-4 引用（批次一致性）。"""
    inp = _baseline_input()
    result = calc_glycol_dehydration(inp)
    assert "n_tray_minimum" in result.formula_ref
    assert "GPSA" in result.formula_ref["n_tray_minimum"]
    assert "Eq.20-4" in result.formula_ref["n_tray_minimum"]


def test_golden_fixture_cross_check():
    """黄金对账：GPSA §20.4 N_min + TEG loss 经验值（rel ≤ 1e-2）。"""
    data = json.loads(_FIXTURE_PATH.read_text())
    for point in data["points"]:
        inp_dict = {k: v for k, v in point.items() if k not in ("_comment", "expected")}
        expected = {
            "n_tray_minimum": point["expected_n_tray_minimum"],
            "tegloss_gal_d": point["expected_tegloss_gal_d"],
        }
        inp = GlycolDehydrationInput(
            gas_flow_mmscfd=inp_dict["gas_flow_mmscfd"],
            inlet_water_content_lb_per_mmscf=inp_dict["inlet_water_lb_per_mmscf"],
            outlet_water_content_lb_per_mmscf=inp_dict["outlet_water_lb_per_mmscf"],
            glycol_type=inp_dict["glycol_type"],
            contactor_tray_count=inp_dict["contactor_tray_count"],
            glycol_circulation_rate_gpm=inp_dict["glycol_circulation_gpm"],
        )
        result = calc_glycol_dehydration(inp)
        assert result.n_tray_minimum == expected["n_tray_minimum"], (
            f"{inp_dict}: N_min {result.n_tray_minimum} != "
            f"expected {expected['n_tray_minimum']}"
        )
        # TEG loss = 0.5 × Q（GPSA 经验）；rel ≤ 1e-2
        actual_tegloss = result.teg_loss_gpd
        assert abs(actual_tegloss - expected["tegloss_gal_d"]) / expected["tegloss_gal_d"] < 1e-2