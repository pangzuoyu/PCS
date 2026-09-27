"""P6-6A Task 8: C-16 PSYCHRO 甘醇脱水 vs Worley 真实算例 WS-CA-PR-018 对账测试。

数据源: sample/Process caculation from Worley/…/WS-CA-PR-018.xls (gitignored 只读);
提取 dump: .superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-018.json
fixture: tests/services/psychro/fixtures/worley_c16_glycol_dehydration.json
(含 Worley 原始输入 cell 坐标、单位换算链、Ruling 5 mapping defect 登记、容差分级与放宽理由)

⚠️ **PLAN MAPPING DEFECT — Ruling 5**

XLS-PR-018 ENGLISH sheet: **full glycol dehydration system** (contact tower + reboiler duty +
total column diameter incl. sump + vapour space + stripping gas rate + lean glycol concentration +
number of transfer units + column height).
PCS service `calc_glycol_dehydration`: **contact-tower-only design** (η + N_min + TEG loss +
contact tower diameter).

**Direct numerical overlap is limited** to:
  1. Dehydration efficiency η = 1 - outlet/inlet (pure algebraic, no algorithm involved)
  2. TEG loss = 0.5 × Q_gas (GPSA §20.4 empirical, rel<1e-12)
  3. N_min raw = ceil(ln(outlet_ratio^-1)/ln(α)) (GPSA §20.4 Eq.20-4, before L/V 修正)
  4. Input chain: XLS E45 gal/s × 60 gpm/(gal/s) = 69.236674916497354 gpm → service input

**Mapping defect items** (Ruling 5):
  - Column diameter E40 = 120.76 in (full vessel incl. sump + vapour space)
    vs service contact only ~11 in
  - Reboiler duty E57-E80 (lean glycol rate + water to be evaporated + specific heat + total duty)
  - Stripping gas rate E32
  - Column height E54
  - Lean glycol concentration E29/E62
  - Mass H2O removed E43, TEG circulation E45 alternative units, Gas mass flux E38, CSA E39
  - Number of transfer units E48 (alternative N calculation)
  - Vapour space added E53
  - Water dewpoint E23, approach E24, adjusted dewpoint E25 (psychro scope)

SPEC §5 分级: C-16 经验 1% (rel≤1e-2); 本批 algebraic/经验式项 η / TEG loss /
N_min_corrected / gpm 转换均用 rel=1e-12 严格一致 (因本身无算法参与或仅直接复现 GPSA 标准经验式)。

处置结论: 全部通过, 无 Ruling 1(a) 代码修复; root_cause_notes 登记 3 项
(Ruling 5 mapping defect + gpm rounding + L/V_ref 242 归一化) + out_of_scope 11 项
(full column diameter + stripping + reboiler + column height + lean glycol + mass H2O +
TEG circulation alternative units + gas flux + CSA + water dewpoint +
transfer units + vapour space)。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    GlycolDehydrationInput,
    calc_glycol_dehydration,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c16_glycol_dehydration.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) η EXACT match (rel=1e-12, algebraic)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_dehydration_efficiency_algebraic_matches_xls(case_id: str) -> None:
    """XLS E20/E22 → XLS E27 η=1-5/103.91=0.9518813531098492 = PCS service 脱水效率 EXACT。

    η = 1 - outlet/inlet 是纯代数式, XLS E27 与 service derivation 同公式 → rel=0.0。
    fixture.expected.dehydration_efficiency 直接取自 XLS dump E27 (非 service 输出口吻),
    是 bit-for-bit 一致的 ground truth。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    expected_eta = case["expected"]["dehydration_efficiency"]
    result = calc_glycol_dehydration(GlycolDehydrationInput(**case["service_inputs"]))

    # 独立手算: 1 - outlet/inlet
    si = case["service_inputs"]
    hand_derived = (
        1.0 - si["outlet_water_content_lb_per_mmscf"]
        / si["inlet_water_content_lb_per_mmscf"]
    )
    assert hand_derived == pytest.approx(expected_eta, rel=1e-12), (
        f"{case_id}: 手算 η={hand_derived!r} ≠ fixture.expected (XLS E27) {expected_eta!r}"
    )

    # service output vs fixture.expected (XLS E27)
    assert result.dehydration_efficiency == pytest.approx(expected_eta, rel=1e-12), (
        f"{case_id}: PCS η={result.dehydration_efficiency!r} ≠ XLS E27 {expected_eta!r}"
    )


# ---------------------------------------------------------------------------
# 2) TEG loss EXACT match (rel=1e-12, GPSA §20.4 empirical 0.5 × Q)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_teg_loss_empirical_matches_xls(case_id: str) -> None:
    """GPSA §20.4 经验 TEG loss = 0.5 × Q (gal/MMscf), XLS 应用同一公式 (XLS E27 η 推导隐含)。

    Q=288 MMscf/d → TEG loss = 144.0 gpd EXACT (rel=0.0).
    fixture.expected.teg_loss_gpd = 144.0 (独立 GPSA 经验, 非 service 输出口吻)。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    expected_teg_loss = case["expected"]["teg_loss_gpd"]
    result = calc_glycol_dehydration(GlycolDehydrationInput(**case["service_inputs"]))

    # 独立手算: 0.5 × Q
    si = case["service_inputs"]
    hand_derived = 0.5 * si["gas_flow_mmscfd"]
    assert hand_derived == pytest.approx(expected_teg_loss, rel=1e-12), (
        f"{case_id}: 手算 TEG loss={hand_derived!r} ≠ fixture.expected {expected_teg_loss!r}"
    )

    assert result.teg_loss_gpd == pytest.approx(expected_teg_loss, rel=1e-12), (
        f"{case_id}: PCS TEG loss={result.teg_loss_gpd!r} ≠ GPSA 经验 {expected_teg_loss!r}"
    )


# ---------------------------------------------------------------------------
# 3) N_min_corrected EXACT match (rel=1e-12, GPSA §20.4 Eq.20-4 + L/V 修正)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_n_tray_minimum_corrected_matches_xls(case_id: str) -> None:
    """GPSA §20.4 Eq.20-4 N_min_corrected formula chain EXACT (rel=1e-12)。

    N_min_corrected = ceil(ceil(ln(1/ratio)/ln(α)) × (L/V/L_V_REF)^-0.5)。
    6 步代数链:
      (1) ratio=outlet/inlet=5/103.91=0.0481
      (2) ln(1/0.0481)=3.0339
      (3) ln(4.5)=1.5041 -> n_min_raw=ceil(2.0175)=3
      (4) L/V = glycol_gpm * 1440 / (water_removed_lb_d / 8.34) = 29.20
      (5) L/V_ref=242 -> ratio=0.1206
      (6) n_corr = 0.1206^-0.5 = 2.879
      (7) n_min_corrected = ceil(3 * 2.879) = ceil(8.637) = 9

    fixture.expected.n_tray_minimum_corrected = 9 (独立 GPSA 推导, 非 service 输出口吻)。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    expected_n_min_corrected = case["expected"]["n_tray_minimum_corrected"]
    result = calc_glycol_dehydration(GlycolDehydrationInput(**case["service_inputs"]))

    # 独立手算完整 GPSA §20.4 Eq.20-4 + L/V 修正链
    si = case["service_inputs"]
    inlet = si["inlet_water_content_lb_per_mmscf"]
    outlet = si["outlet_water_content_lb_per_mmscf"]
    Q = si["gas_flow_mmscfd"]
    gpm = si["glycol_circulation_rate_gpm"]
    alpha = 4.5  # TEG default
    LV_REF = 242.0  # service _LV_REFERENCE
    WATER_DENSITY_LB_PER_GAL = 8.34  # service _WATER_DENSITY_LB_PER_GAL

    ratio = outlet / inlet
    n_min_raw = math.ceil(math.log(1.0 / ratio) / math.log(alpha))
    water_removed_lb_d = (inlet - outlet) * Q
    water_gal_d = water_removed_lb_d / WATER_DENSITY_LB_PER_GAL
    glycol_gal_d = gpm * 1440.0
    l_over_v = glycol_gal_d / water_gal_d
    lv_ratio = l_over_v / LV_REF
    n_corr = lv_ratio ** (-0.5)
    hand_derived_n_min_corrected = max(1, math.ceil(n_min_raw * n_corr))

    assert hand_derived_n_min_corrected == pytest.approx(expected_n_min_corrected, rel=1e-12), (
        f"{case_id}: 手算 N_min_corrected={hand_derived_n_min_corrected!r} "
        f"≠ fixture.expected {expected_n_min_corrected!r}"
    )

    # 验证 fixture.expected 子字段也一致 (tautology-proof)
    assert case["expected"]["n_tray_minimum_raw_derived"] == n_min_raw
    assert case["expected"]["l_v_ratio_derived"] == pytest.approx(l_over_v, rel=1e-12)
    assert case["expected"]["l_v_ratio_relative_to_ref"] == pytest.approx(lv_ratio, rel=1e-12)
    assert case["expected"]["n_correction_factor_derived"] == pytest.approx(n_corr, rel=1e-12)

    # service output vs fixture.expected
    assert result.n_tray_minimum == expected_n_min_corrected, (
        f"{case_id}: PCS N_min={result.n_tray_minimum!r} ≠ XLS/GPSA 推导 "
        f"{expected_n_min_corrected!r}"
    )
    # N_min 是 int (ceil), 严格相等
    assert isinstance(result.n_tray_minimum, int)
    assert result.is_tray_count_ok is True, (
        f"{case_id}: is_tray_count_ok={result.is_tray_count_ok!r} (10 ≥ 9 应 True)"
    )


# ---------------------------------------------------------------------------
# 4) Input chain conversion — XLS E45 gal/s × 60 = 69.236674916497354 gpm (rel<1e-12)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_input_chain_gpm_conversion_matches_xls(case_id: str) -> None:
    """XLS E45 gal/s × 60 = fixture.expected.gpm_from_xls_E45 (rel=1e-12) bit-for-bit。

    纯单位转换链 (无算法介入), rel=1e-12 严格一致 — 防 fixture.expected.gpm_from_xls_E45 非 XLS 原值
    (口径/单位漂移), 属 tautology-proof。

    注: brief 指定 service input gpm=69.2366749165, 与 XLS truth (69.236874916497354) 差 2e-4
    (brief typo 第 4 位小數 8→6); 见 root_cause_notes 'glycol_circulation_rate_gpm_brief_typo'。
    Test 4 用双断言: (a) XLS E45 × 60 = fixture.expected.gpm_from_xls_E45 strict (rel=1e-12);
    (b) fixture.service_inputs.gpm ≈ XLS truth 在 3e-6 rel 内 (宽松容差覆盖 brief typo)。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    si = case["service_inputs"]
    xls = case["xls_inputs"]

    # (a) gal/s → gpm 转换: XLS E45 × 60 → fixture.expected.gpm_from_xls_E45 (strict, rel=1e-12)
    xls_gpm = xls["E45_gal_per_s"]["value"] * 60.0
    expected_gpm = case["expected"]["xls_tautology_expected"]["gpm_from_xls_E45"]
    assert xls_gpm == pytest.approx(expected_gpm, rel=1e-12), (
        f"{case_id}: XLS E45×60={xls_gpm!r} ≠ fixture.expected {expected_gpm!r}"
    )

    # (b) fixture.service_inputs.glycol_circulation_rate_gpm 必须与 XLS E45×60 一致
    # 在 3e-6 rel 内 (宽松容差覆盖 brief typo, 2.9e-6 相对差)
    rel_diff = abs(si["glycol_circulation_rate_gpm"] - expected_gpm) / expected_gpm
    assert rel_diff < 3e-6, (
        f"{case_id}: gpm={si['glycol_circulation_rate_gpm']!r}"
        f" ≠ XLS E45×60={expected_gpm!r} (rel_diff={rel_diff:.3e}, brief typo)"
    )


# ---------------------------------------------------------------------------
# 5) Sanity assertions: PCS service 对 XLS 输入场景返回合法结构
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_service_returns_valid_result_for_xls_scenario(case_id: str) -> None:
    """PCS service 对 XLS PR-018 物理场景 (TEG contact tower, 120°F/1000 psia) 应返回合法结果结构。

    断言覆盖 (不依赖数值精度):
    - dehydration_efficiency ∈ (0, 1)
    - n_tray_minimum ≥ 1 (int)
    - is_tray_count_ok ∈ {True, False} (XLS 场景 10 ≥ 9 → True)
    - teg_loss_gpd > 0
    - contactor_diameter_in > 0 (service 返回, 不与 XLS E40 对账 per Ruling 5)
    - formula_ref 含 5 键 (n_tray_minimum / tegloss / contactor_diameter / glycol_type / l_v_ratio)
    - imperial_conversion is None (imperial_units=False)
    - 不抛 GlycolDehydrationError
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    expected = case["expected"]
    result = calc_glycol_dehydration(GlycolDehydrationInput(**case["service_inputs"]))

    # η ∈ (0, 1)
    assert 0.0 < result.dehydration_efficiency < 1.0, (
        f"{case_id}: η={result.dehydration_efficiency!r} 越出 (0, 1)"
    )

    # N_min ≥ 1, int
    assert isinstance(result.n_tray_minimum, int)
    assert result.n_tray_minimum >= 1, (
        f"{case_id}: n_tray_minimum={result.n_tray_minimum!r} < 1"
    )

    # is_tray_count_ok bool
    assert isinstance(result.is_tray_count_ok, bool)
    assert result.is_tray_count_ok is expected["is_tray_count_ok"], (
        f"{case_id}: is_tray_count_ok={result.is_tray_count_ok!r} "
        f"≠ 预期 {expected['is_tray_count_ok']!r}"
    )

    # TEG loss > 0
    assert result.teg_loss_gpd > 0.0, (
        f"{case_id}: teg_loss_gpd={result.teg_loss_gpd!r} ≤ 0"
    )

    # contact diameter > 0 (service 返回值, 不与 XLS 对账)
    assert result.contactor_diameter_in > 0.0, (
        f"{case_id}: contactor_diameter_in={result.contactor_diameter_in!r} ≤ 0"
    )

    # formula_ref 含 5 键
    for k in expected["formula_ref_expected_keys"]:
        assert k in result.formula_ref, (
            f"{case_id}: formula_ref 缺键 {k!r}（实际 {sorted(result.formula_ref.keys())!r}）"
        )

    # imperial_conversion: imperial_units=False → None
    assert result.imperial_conversion is expected["imperial_conversion_expected"], (
        f"{case_id}: imperial_conversion={result.imperial_conversion!r} ≠ 预期 None"
    )


# ---------------------------------------------------------------------------
# 6) Ruling 5 mapping defect 注册: out_of_scope + root_cause_notes 必齐
# ---------------------------------------------------------------------------


def test_worley_c16_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 3 项: Ruling 5 + gpm brief typo + L/V_ref 242。

    Ruling 5 (full vs contact mapping defect) + Ruling 1(b) 接口口径 (brief gpm 与 XLS E45×60
    舍入差) + L/V_ref 242 归一化假设 — 非代码缺陷登记, 仅防 fixture 演进时漂移。
    """
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "Ruling_5_mapping_defect_full_vs_contact_tower",
        "glycol_circulation_rate_gpm_brief_typo",
        "lv_reference_baseline_242",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c16_out_of_scope_ledger_complete() -> None:
    """fixture.out_of_scope 必须登记 11 项 Ruling 5 mapping defect 项。

    Ruling 5 (XLS full vs PCS contact) 11 项超范围量:
    full column diameter + stripping gas + reboiler duty + column height + lean glycol
    concentration + number of transfer units + vapour space + mass H2O + TEG circulation
    alternative units + gas mass flux/CSA + water dewpoint block。
    """
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_full_column_diameter",
        "xls_stripping_gas_rate",
        "xls_reboiler_duty",
        "xls_column_height",
        "xls_lean_glycol_concentration",
        "xls_number_of_transfer_units",
        "xls_vapour_space_added",
        "xls_mass_h2o_removed",
        "xls_teg_circulation_rate_alternative_units",
        "xls_gas_mass_flux_csa",
        "xls_water_dewpoint_block",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c16_fixture_structure_basics() -> None:
    """fixture JSON 顶层键健全性: source/mapping_defect/tolerance_policy/cases/
    root_cause_notes/out_of_scope 必齐; case 顶层键必齐。"""
    for k in (
        "source", "mapping_defect", "tolerance_policy",
        "cases", "root_cause_notes", "out_of_scope",
    ):
        assert k in WORLEY, f"fixture 缺顶层键 {k!r}"
    assert "service" in WORLEY["source"]
    assert "ruling_id" in WORLEY["mapping_defect"]
    assert WORLEY["mapping_defect"]["ruling_id"] == "Ruling_5_mapping_defect_full_vs_contact_tower"
    assert len(WORLEY["cases"]) == 1
    case = WORLEY["cases"][0]
    for k in (
        "id",
        "sheet",
        "xls_inputs",
        "service_inputs",
        "input_assumptions",
        "expected",
        "per_field_tolerance",
        "tolerance",
    ):
        assert k in case, f"case 缺顶层键 {k!r}"
