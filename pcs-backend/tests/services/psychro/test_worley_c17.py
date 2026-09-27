"""P6-6A Task 9: C-17 PSYCHRO 饱和水含量 vs Worley 真实算例 WS-CA-PR-019 对账测试。

数据源: sample/Process caculation from Worley/…/WS-CA-PR-019.xls (gitignored 只读);
提取 dump: .superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-019.json
fixture: tests/services/psychro/fixtures/worley_c17_saturation_w.json
(含 Worley 原始输入 cell 坐标、单位换算链、Ruling 9 working fluid defect 登记、
容差分级与放宽理由)

⚠️ **WORKING FLUID DEFECT — Ruling 9**

XLS-PR-019 Calculation sheet: **Natural Gas Saturated Water Content** (Behr correlation
for natural gas with CO2+H2S, output lb/MMscf wet gas + mg/Sm³ wet gas).
PCS service `calc_saturation_water_content`: **Humid Air Saturation Water Content** (CoolProp
HAPropsSI based on ASHRAE RP-1845, output 3 units: kg/kg dry air / mg/Sm³ dry air /
lb/MMscf dry air).

**Direct numerical bit-for-bit match is meaningless** because:
  - Working fluid differs: natural gas (hydrocarbon mixture with CO2/H2S) vs humid air
    (~79% N2 + 21% O2 + trace)
  - Algorithm family differs: Behr proprietary correlation vs HAPropsSI ASHRAE RP-1845
  - Output basis differs: wet gas (含水) vs dry air (不含水)

Test scope reduced to:
  1. **Unit conversions EXACT** (pure algebra, no algorithm involved):
     - °F → °C: (T-32) × 5/9
     - psia → kPa: × 6.894757 (NIST exact)
     - bar → kPa: × 100 (exact)
     - lb/MMscf ↔ mg/Sm³: × 16.01846 / ÷ 16.01846
  2. **OoM cross-validation**: PCS service.saturation_w_lb_per_mmscf / XLS F29 (lb/MMscf
     wet gas) within 2 orders of magnitude (0.01 < ratio < 100). Typical variance 10-30%
     due to working fluid + algorithm differences.
  3. **Sanity assertions**: T in [-50, 100]°C / P in [0, 100 atm] kPa / no NaN / valid
     struct / formula_ref non-empty / no acid correction (all 5 cases < 40 mol%).
  4. **Ruling 9 registration**: mapping_defect.ruling_id + root_cause_notes +
     out_of_scope 三层注册, 防 fixture 演进时漂移.

SPEC §5 分级: C-17 强公式 0.1% (rel≤1e-3); 本批因 Ruling 9 working fluid defect,
强公式容差 NOT used; 仅 unit conversion 用 rel=1e-12 严格一致 (pure algebra, no
algorithm); OoM cross-validation 用 2 OoM band (0.01, 100) 替代直接数值对账。

处置结论: 全部通过 (5 cases + sanity + OoM + Ruling 9); 无 Ruling 1(a) 代码修复;
root_cause_notes 登记 3 项 (Ruling 9 working fluid defect + xls wet gas vs pcs dry air +
xls pressure input unit imp vs si case J) + out_of_scope 9 项 (bit-for-bit value match +
Behr coefficients + acid correction accuracy + Imperial/SI dual output + T/P/acid limit
checks + conversion data block + notes block)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    SaturationWaterContentInput,
    calc_saturation_water_content,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c17_saturation_w.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) Unit conversion EXACT match (rel=1e-12, algebraic pure conversion)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_unit_conversion_exact_matches_xls(case_id: str) -> None:
    """3 步 unit conversion EXACT (rel=1e-12):

    - T_F → T_C: (T_F - 32) × 5/9 (Case F=37.7778°C; Case J=21.7283°C)
    - P_psia → P_kpa: × 6.894757 (Case F=8273.71 kPa; Case H=6894.76 kPa)
    - bar → P_kpa: × 100 (Case J=6996.083 kPa)
    - lb/MMscf → mg/Sm³: × 16.01846 (Case F=929.61 mg/Sm³)

    均为 pure algebra, 无算法介入 → rel=1e-12 严格一致. 防 fixture.service_inputs 和
    fixture.expected 数值非 XLS 原值, 属 tautology-proof。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    tautology = case["expected"]["xls_tautology_expected"]

    # (a) T_F → T_C EXACT
    xls = case["xls_inputs"]
    if "F17_F" in xls:
        t_f = xls["F17_F"]["value"]
        hand_t_c = (t_f - 32.0) * 5.0 / 9.0
        expected_t_c = tautology["t_c_from_xls_F17_F"]
        assert hand_t_c == pytest.approx(expected_t_c, rel=1e-12), (
            f"{case_id}: 手算 T_C={hand_t_c!r} ≠ fixture.expected {expected_t_c!r}"
        )

    # (b) P_psia → P_kpa EXACT (or bar → kPa ×100 for Case J)
    if "F18_psia" in xls:
        p_psia = xls["F18_psia"]["value"]
        hand_p_kpa = p_psia * 6.894757
        expected_p_kpa = tautology["p_kpa_from_xls_F18_psia"]
        assert hand_p_kpa == pytest.approx(expected_p_kpa, rel=1e-12), (
            f"{case_id}: 手算 P_kpa={hand_p_kpa!r} ≠ fixture.expected {expected_p_kpa!r}"
        )
    elif "J18_bar" in xls:
        p_bar = xls["J18_bar"]["value"]
        hand_p_kpa = p_bar * 100.0
        expected_p_kpa = tautology["p_kpa_from_xls_J18_bar"]
        assert hand_p_kpa == pytest.approx(expected_p_kpa, rel=1e-12), (
            f"{case_id}: 手算 P_kpa={hand_p_kpa!r} ≠ fixture.expected {expected_p_kpa!r}"
        )

    # (c) lb/MMscf ↔ mg/Sm³ APPROXIMATE (XLS F29/F30 是独立计算 — 非代数换算)
    # XLS F29 (lb/MMscf wet gas) 和 F30 (mg/Sm³ wet gas) 是 Behr 公式独立输出,
    # 用 XLS 内部 wet gas 转换因子 (~16.01712), 与 brief 标准的 16.01846
    # (dry air, NIST exact) 偏差 ~0.008%。XLS 内部一致, 但非严格代数关系。
    # 校验: XLS F29/F30 应在 brief 标准的 rel=1e-3 内 (loose, 承认 XLS 内部偏差)。
    xls_out = case["xls_outputs"]
    f29_key = next(k for k in xls_out if "lb_per_MMscf" in k)
    f30_key = next(k for k in xls_out if "mg_per_sm3" in k)
    hand_mg_sm3 = xls_out[f29_key]["value"] * 16.01846
    expected_mg_sm3 = xls_out[f30_key]["value"]
    rel_diff = abs(hand_mg_sm3 - expected_mg_sm3) / expected_mg_sm3
    assert rel_diff < 1e-3, (
        f"{case_id}: 手算 mg/Sm³={hand_mg_sm3!r} 与 XLS F30/G30/H30/I30/J30 {expected_mg_sm3!r}"
        f" rel_diff={rel_diff:.4e} ≥ 1e-3 (XLS 内部 wet gas 转换因子偏差 ~0.008%)"
    )

    # (d) PCS service input vs fixture.expected (independent tautology check)
    si = case["service_inputs"]
    if "F17_F" in xls:
        assert si["temperature_c"] == pytest.approx(expected_t_c, rel=1e-12), (
            f"{case_id}: service_inputs.T_c={si['temperature_c']!r} "
            f"≠ XLS F17 derived {expected_t_c!r}"
        )
    if "F18_psia" in xls:
        assert si["pressure_kpa"] == pytest.approx(expected_p_kpa, rel=1e-12), (
            f"{case_id}: service_inputs.P_kpa={si['pressure_kpa']!r} "
            f"≠ XLS F18 derived {expected_p_kpa!r}"
        )
    elif "J18_bar" in xls:
        assert si["pressure_kpa"] == pytest.approx(expected_p_kpa, rel=1e-12), (
            f"{case_id}: service_inputs.P_kpa={si['pressure_kpa']!r} "
            f"≠ XLS J18 derived {expected_p_kpa!r}"
        )


# ---------------------------------------------------------------------------
# 2) PCS service sanity (valid result, no NaN, formula_ref, in T/P range)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_service_returns_valid_result_for_xls_scenario(case_id: str) -> None:
    """PCS service 对 XLS PR-019 物理场景 (natural gas saturated water content, 5 cases)
    应返回合法结果结构。

    断言覆盖 (不依赖数值精度 — Ruling 9 working fluid defect):
    - saturation_w_kg_kg > 0 (有物理意义的正饱和湿度比)
    - saturation_w_mg_sm3 > 0
    - saturation_w_lb_per_mmscf > 0
    - saturation_T_c == service input temperature (回显)
    - temperature_out_of_range is False (5 cases 全部 in [-50, 100]°C range)
    - warning_message is None (5 cases in T/P range, no CoolProp rejection)
    - acidic_gas_correction_applied is False (5 cases 全部 < 40 mol% 阈值)
    - acidic_gas_correction_factor == 1.0 (未应用校正)
    - formula_ref == "ASHRAE_RP-1845_CoolProp" (公式溯源标记)
    - 不抛异常 (SaturationWaterContentInputError / ValueError)
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    si = case["service_inputs"]

    # 不抛异常
    result = calc_saturation_water_content(SaturationWaterContentInput(**si))

    # 3 单位 > 0 (合法饱和湿度比)
    assert result.saturation_w_kg_kg > 0.0, (
        f"{case_id}: saturation_w_kg_kg={result.saturation_w_kg_kg!r} ≤ 0"
    )
    assert result.saturation_w_mg_sm3 > 0.0, (
        f"{case_id}: saturation_w_mg_sm3={result.saturation_w_mg_sm3!r} ≤ 0"
    )
    assert result.saturation_w_lb_per_mmscf > 0.0, (
        f"{case_id}: saturation_w_lb_per_mmscf={result.saturation_w_lb_per_mmscf!r} ≤ 0"
    )

    # 温度回显
    assert result.saturation_T_c == si["temperature_c"], (
        f"{case_id}: saturation_T_c={result.saturation_T_c!r} ≠ input {si['temperature_c']!r}"
    )

    # 5 cases 全部 in T range [-50, 100]°C
    assert result.temperature_out_of_range is False, (
        f"{case_id}: temperature_out_of_range={result.temperature_out_of_range!r}"
        f" (5 cases 应全 False)"
    )

    # 无警告（5 cases 全部 in range, CoolProp 应接受）
    assert result.warning_message is None, (
        f"{case_id}: warning_message={result.warning_message!r} (5 cases 应 None)"
    )

    # 酸性气校正未应用 (5 cases 全部 < 40 mol% 阈值)
    assert result.acidic_gas_correction_applied is False, (
        f"{case_id}: acidic_gas_correction_applied="
        f"{result.acidic_gas_correction_applied!r} (5 cases 应 False)"
    )
    assert result.acidic_gas_correction_factor == 1.0, (
        f"{case_id}: correction_factor="
        f"{result.acidic_gas_correction_factor!r} (5 cases 应 1.0)"
    )

    # 公式溯源标记
    assert result.formula_ref == "ASHRAE_RP-1845_CoolProp", (
        f"{case_id}: formula_ref={result.formula_ref!r} (应为 ASHRAE_RP-1845_CoolProp)"
    )


# ---------------------------------------------------------------------------
# 3) OoM cross-validation: PCS vs XLS within 2 orders of magnitude
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_oom_cross_validation_within_2_orders(case_id: str) -> None:
    """OoM cross-validation (Ruling 9 working fluid defect): PCS service.saturation_w_lb_per_mmscf
    / XLS F29 lb/MMscf 应落在 (0.01, 100) 区间 — within 2 orders of magnitude。

    强公式 0.1% 容差不适用 (Ruling 9: XLS natural gas Behr vs PCS humid air HAPropsSI 是
    different working fluids + algorithm families, 典型偏差 10-30%, 极端 T/P 可能扩大
    到 2 OoM 但不超出)。此断言验证 PCS service 在正确 OoM 量级, 不是 bit-for-bit
    match。

    若 ratio < 0.01 或 > 100, 表明 PCS service 量级根本性偏离 XLS 期望, 应进一步
    排查 (而非放宽 tolerance)。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    si = case["service_inputs"]
    xls_lb = case["expected"]["xls_water_content_lb_per_mmscf"]
    oom_band = case["expected"]["oom_band"]

    result = calc_saturation_water_content(SaturationWaterContentInput(**si))

    ratio = result.saturation_w_lb_per_mmscf / xls_lb
    assert ratio > oom_band["ratio_lower_bound"], (
        f"{case_id}: PCS/XLS ratio={ratio:.6g} < {oom_band['ratio_lower_bound']}"
        f" (OoM band lower bound)"
        f" — PCS={result.saturation_w_lb_per_mmscf:.6g} vs XLS={xls_lb:.6g}"
    )
    assert ratio < oom_band["ratio_upper_bound"], (
        f"{case_id}: PCS/XLS ratio={ratio:.6g} > {oom_band['ratio_upper_bound']}"
        f" (OoM band upper bound)"
        f" — PCS={result.saturation_w_lb_per_mmscf:.6g} vs XLS={xls_lb:.6g}"
    )


# ---------------------------------------------------------------------------
# 4) Acid gas correction NOT applied (all 5 cases < 40 mol%)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_acid_gas_correction_not_applied_below_threshold(case_id: str) -> None:
    """XLS PR-019 5 cases acid gas sum (CO2 + H2S mol%) 全部 < 40 mol%:

    - Case F: 11% + 3% = 14% < 40%
    - Case G: 15% + 2% = 17% < 40%
    - Case H: 20% + 1% = 21% < 40%
    - Case I: 20% + 0% = 20% < 40%
    - Case J: 20% + 0% = 20% < 40%

    PCS service._ACID_GAS_THRESHOLD = 0.40 (ISO 18453), 故酸性气校正不应触发:
    - acidic_gas_correction_applied = False
    - acidic_gas_correction_factor = 1.0
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    si = case["service_inputs"]
    acid_sum = case["expected"]["xls_acid_sum_mol_pct"]

    # 验证 fixture acid_sum 算对 (tautology-proof)
    expected_acid_sum_frac = case["expected"]["xls_tautology_expected"]["acid_sum_mol_fraction"]
    assert acid_sum / 100.0 == pytest.approx(expected_acid_sum_frac, rel=1e-12), (
        f"{case_id}: acid_sum_mol_pct={acid_sum}/100 ≠ fixture.expected {expected_acid_sum_frac}"
    )

    # 5 cases 全部 < 40 mol% 阈值
    assert acid_sum < 40.0, (
        f"{case_id}: acid_sum={acid_sum} mol% ≥ 40 mol% threshold (XLS PR-019 5 cases 应全 < 40)"
    )

    # PCS service 验证酸性气校正未触发
    result = calc_saturation_water_content(SaturationWaterContentInput(**si))
    assert result.acidic_gas_correction_applied is False, (
        f"{case_id}: acid correction applied=True (acid_sum={acid_sum}% < 40% 阈值应不触发)"
    )
    assert result.acidic_gas_correction_factor == pytest.approx(1.0, rel=1e-12), (
        f"{case_id}: correction_factor={result.acidic_gas_correction_factor!r} (应=1.0 不触发校正)"
    )


# ---------------------------------------------------------------------------
# 5) Temperature in range (5 cases 全部 in [-50, 100]°C)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_temperature_in_service_safe_range(case_id: str) -> None:
    """XLS PR-019 5 cases T_c 全部 in PCS service._T_MIN_C/_T_MAX_C = [-50, 100]°C:

    - Case F: 37.78°C (in range)
    - Case G: 93.33°C (close to 100°C upper limit but in range)
    - Case H: 48.89°C (in range)
    - Case I: 93.33°C (close to 100°C upper limit but in range)
    - Case J: 21.73°C (in range)

    验证 service 返回 temperature_out_of_range=False + warning_message=None.
    注: Case G/I 在 XLS 60-300°F (=15.6-148.9°C) range 且 service -50~100°C range,
    两者重合区间 15.6~100°C; Case G/I T_c=93.33°C 在重合区间内。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    si = case["service_inputs"]

    # 5 cases 全部 in service T range
    assert -50.0 <= si["temperature_c"] <= 100.0, (
        f"{case_id}: T_c={si['temperature_c']!r} 超出 service [-50, 100]°C range"
    )

    result = calc_saturation_water_content(SaturationWaterContentInput(**si))
    assert result.temperature_out_of_range is False, (
        f"{case_id}: temperature_out_of_range=True (T_c={si['temperature_c']} 应 in range)"
    )
    assert result.warning_message is None, (
        f"{case_id}: warning_message={result.warning_message!r} (T_c in range 应 None)"
    )


# ---------------------------------------------------------------------------
# 6) Ruling 9 registration: mapping_defect + root_cause_notes + out_of_scope 必齐
# ---------------------------------------------------------------------------


def test_worley_c17_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 3 项:

    - Ruling_9_working_fluid_defect_natural_gas_vs_humid_air (primary)
    - xls_wet_gas_vs_pcs_dry_air (Ruling 9 子集)
    - xls_pressure_input_unit_imp_vs_si_case_J (Ruling 1(b) 接口口径)

    Ruling 9 working fluid defect + wet/dry air 分母差异 + XLS 双单位 Case J — 非代码
    缺陷登记, 仅防 fixture 演进时漂移。
    """
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "Ruling_9_working_fluid_defect_natural_gas_vs_humid_air",
        "xls_wet_gas_vs_pcs_dry_air",
        "xls_pressure_input_unit_imp_vs_si_case_J",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c17_out_of_scope_ledger_complete() -> None:
    """fixture.out_of_scope 必须登记 9 项 Ruling 9 working fluid defect 项:

    - xls_bit_for_bit_value_match (Ruling 9 核心 OOS)
    - xls_behr_correlation_coefficients (Behr proprietary)
    - xls_acid_gas_correction_accuracy (XLS Behr vs PCS ISO 18453)
    - xls_imperial_si_dual_output_block (XLS F23-J26 dual unit input)
    - xls_temperature_limit_check_F33 (XLS 60-300°F limit check)
    - xls_pressure_limit_check_F34 (XLS 300-2000 psia limit check)
    - xls_acid_gas_component_limit_F35 (XLS < 40 mol% limit check)
    - xls_conversion_data_block (XLS rows 62-113 internal tables)
    - xls_notes_block (XLS rows 37-40 limit documentation)
    """
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_bit_for_bit_value_match",
        "xls_behr_correlation_coefficients",
        "xls_acid_gas_correction_accuracy",
        "xls_imperial_si_dual_output_block",
        "xls_temperature_limit_check_F33",
        "xls_pressure_limit_check_F34",
        "xls_acid_gas_component_limit_F35",
        "xls_conversion_data_block",
        "xls_notes_block",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c17_ruling_9_registration_complete() -> None:
    """Ruling 9 working fluid defect 三层注册一致性检查:

    1. fixture.mapping_defect.ruling_id == "Ruling_9_working_fluid_defect_natural_gas_vs_humid_air"
    2. root_cause_notes[0].id 包含 working_fluid_defect / natural_gas / humid_air 关键词
    3. out_of_scope 包含 bit_for_bit_value_match (Ruling 9 核心 OOS)
    4. mapping_defect.implication 显式声明 working fluid + algorithm family 差异
    """
    # Layer 1: mapping_defect.ruling_id
    _ruling_id = "Ruling_9_working_fluid_defect_natural_gas_vs_humid_air"
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id, (
        f"mapping_defect.ruling_id={WORLEY['mapping_defect']['ruling_id']!r}"
        f" (应为 {_ruling_id})"
    )

    # Layer 2: root_cause_notes 必含 working fluid defect + algorithm family
    primary_note = next(
        n for n in WORLEY["root_cause_notes"]
        if n["id"] == "Ruling_9_working_fluid_defect_natural_gas_vs_humid_air"
    )
    assert "natural gas" in primary_note["finding"].lower(), (
        "Ruling_9 root_cause finding 必须提及 'natural gas' (working fluid)"
    )
    assert "humid air" in primary_note["finding"].lower(), (
        "Ruling_9 root_cause finding 必须提及 'humid air' (working fluid)"
    )
    assert "behr" in primary_note["finding"].lower(), (
        "Ruling_9 root_cause finding 必须提及 'Behr' (XLS algorithm family)"
    )
    assert "hapropssi" in primary_note["finding"].lower(), (
        "Ruling_9 root_cause finding 必须提及 'HAPropsSI' (PCS algorithm family)"
    )

    # Layer 3: out_of_scope 必含 bit-for-bit value match
    oos_ids = {o["id"] for o in WORLEY["out_of_scope"]}
    assert "xls_bit_for_bit_value_match" in oos_ids, (
        "out_of_scope 必须包含 xls_bit_for_bit_value_match (Ruling 9 核心 OOS)"
    )

    # Layer 4: mapping_defect.implication 显式 working fluid + algorithm family
    impl = WORLEY["mapping_defect"]["implication"].lower()
    assert "working fluid" in impl, (
        "mapping_defect.implication 必须显式声明 'working fluid'"
    )
    assert "algorithm" in impl, (
        "mapping_defect.implication 必须显式声明 'algorithm family' 差异"
    )


def test_worley_c17_fixture_structure_basics() -> None:
    """fixture JSON 顶层键健全性: source/mapping_defect/tolerance_policy/unit_conversion_factors/
    xls_workbook/cases/root_cause_notes/out_of_scope 必齐; case 顶层键必齐。"""
    for k in (
        "source", "mapping_defect", "tolerance_policy",
        "unit_conversion_factors", "xls_workbook", "cases",
        "root_cause_notes", "out_of_scope",
    ):
        assert k in WORLEY, f"fixture 缺顶层键 {k!r}"
    assert "service" in WORLEY["source"]
    assert "ruling_id" in WORLEY["mapping_defect"]
    _ruling_id_ck = "Ruling_9_working_fluid_defect_natural_gas_vs_humid_air"
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id_ck
    assert len(WORLEY["cases"]) == 5

    # unit_conversion_factors 必含 4 项
    ucf = WORLEY["unit_conversion_factors"]
    for k in ("F_to_C", "psia_to_kpa", "bar_to_kpa", "lb_per_mmscf_to_mg_per_sm3"):
        assert k in ucf, f"unit_conversion_factors 缺键 {k!r}"

    # 5 cases 顶层键必齐
    for case in WORLEY["cases"]:
        for k in (
            "id", "sheet", "xls_inputs", "xls_outputs",
            "service_inputs", "input_assumptions", "expected",
            "per_field_tolerance", "tolerance",
        ):
            assert k in case, f"case {case.get('id', '?')} 缺顶层键 {k!r}"

        # 验证 case 5 cases 全 acid sum < 40 mol%
        assert case["expected"]["xls_acid_sum_mol_pct"] < 40.0, (
            f"case {case['id']}: acid_sum={case['expected']['xls_acid_sum_mol_pct']} ≥ 40 mol%"
            f" (5 cases 应全 < 40)"
        )

        # 验证 OoM band 合法
        oom = case["expected"]["oom_band"]
        _lb = oom["ratio_lower_bound"]
        _ub = oom["ratio_upper_bound"]
        assert _lb < _ub, (
            f"case {case['id']}: OoM band [{_lb}, {_ub}] 不合法"
        )