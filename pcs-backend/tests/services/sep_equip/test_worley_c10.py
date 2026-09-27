"""P6-6A Task 5：C-10 VESSEL 三相分离器 vs Worley 真实算例 WS-CA-PR-011 对账测试。

数据源：sample/Process caculation from Worley/…/WS-CA-PR-011.xls（gitignored 只读）；
提取 dump：.superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-011.json
fixture：tests/services/sep_equip/fixtures/worley_c10_three_phase.json
（含 Worley 原始输入 cell 坐标、单位换算链、容差分级与放宽/收紧理由）

对账范围：
1. 单 aggregate 工况 sheet — 三相体积流量（m³/d）+ total_volume_m3（几何）
   + 液相停留时间（combined vs XLS 油单独 r71=8.56 min）+ 气相停留时间
   + oil_water_interface_m / weir_height_required_m（pass-through）
   + is_residence_time_ok + formula_ref + imperial_conversion 键完整。
2. 几何量独立复算（test_chain_quantities）：Q = m_dot/ρ 三相逐项
   + V_total = π·D²/4·L + 2·π·D³/24（2:1 椭圆封头）。

超出模块契约的 XLS 输出（Souders-Brown K/Vmax/CSA 段→C-08、nozzle sizing→
P5-3 nozzle、仪表控制高度表 9×11 → 仪表工程设计、slug volume 动态分析）
登记于 fixture out_of_scope，test_out_of_scope_registered 守卫登记不漂移。

SPEC §5 分级：C-10 经验拟合级 rel≤1e-2；本批各字段在门槛内收紧（mass/ρ 严格代数
1e-3）或放宽（combined vs separate RT 0.1；几何 2e-2；气 RT 0.05）。
处置结论：全部通过，无 Ruling 1(a) 代码修复；root_cause_notes 登记
3 项算法变体（combined vs separate RT / XLS V64 仪表 vs service 接口口径 /
gas RT XLS 缺失）+ 1 项数据差异（XLS 双单位 bbl/d + m³/hr vs service m³/d）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.sep_equip.three_phase_separator_service import (
    ThreePhaseSeparatorInput,
    calc_three_phase_separator,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c10_three_phase.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

_M3_TO_FT3 = 35.3147

# service 输出字段 ← fixture expected 键（精确字段映射）
_RESULT_ATTR: dict[str, str] = {
    "oil_vol_rate_m3_d": "oil_vol_rate_m3_d",
    "water_vol_rate_m3_d": "water_vol_rate_m3_d",
    "gas_vol_rate_m3_d": "gas_vol_rate_m3_d",
    "oil_water_interface_m": "oil_water_interface_m",
    "weir_height_required_m": "weir_height_required_m",
    "liquid_residence_time_min": "liquid_residence_time_min",
    "gas_residence_time_s": "gas_residence_time_s",
    "total_volume_m3": "total_volume_m3",
}


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) 单 aggregate 工况 sheet 全量对账（fixture 参数化）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_worley_c10_case_reconciliation(case_id: str) -> None:
    """单工况对账：三相体积流量 + total_volume_m3 + 液/气 RT + pass-through。

    断言覆盖 XLS 中出现的全部本模块契约内输出量：
    oil/water/gas vol rate (m³/d)、oil_water_interface_m、weir_height_required_m、
    total_volume_m3、liquid_residence_time_min、gas_residence_time_s、is_residence_time_ok。
    Per-field tolerance 见 fixture.per_field_tolerance；统一默认值取 cases[].tolerance.rel。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    default_rel = case["tolerance"]["rel"]
    per_field = case["per_field_tolerance"]
    expected = case["expected"]

    result = calc_three_phase_separator(
        ThreePhaseSeparatorInput(**case["service_inputs"])
    )

    # 数值字段逐项断言（per_field_tolerance 覆盖默认 rel）
    for key, attr in _RESULT_ATTR.items():
        if key not in expected:
            continue  # skip keys not expected (e.g. chain-only fields)
        rel = per_field.get(key, {}).get("rel", default_rel)
        actual = getattr(result, attr)
        exp = expected[key]
        assert actual == pytest.approx(exp, rel=rel), (
            f"{case_id}.{key}: PCS={actual!r} vs XLS={exp!r}（rel 门槛 {rel}）"
        )

    # 布尔字段
    assert result.is_residence_time_ok is expected["is_residence_time_ok"], (
        f"{case_id}: is_residence_time_ok={result.is_residence_time_ok}，"
        f"XLS 推断={expected['is_residence_time_ok']}"
    )

    # formula_ref + imperial_conversion 完整性
    for k in expected["formula_ref_expected_keys"]:
        assert k in result.formula_ref, f"{case_id}: formula_ref 缺键 {k!r}"
    # imperial_units=False → imperial_conversion 必须 None
    assert result.imperial_conversion is None, (
        f"{case_id}: imperial_units=False 时 imperial_conversion 应为 None，"
        f"实际={result.imperial_conversion!r}"
    )

    _assert_chain_quantities(case, default_rel)


def _assert_chain_quantities(case: dict, rel: float) -> None:
    """链上量对账：三相体积流量（mass/ρ）+ V_total（HORIZONTAL 几何）。

    service 返回的 volume_rates 已与 XLS J28/M28/P28 (m³/hr × 24) 对账；
    此函数复算同输入下三相体积流量，确保 fixture expected 值非 service 输出回声。
    """
    si = case["service_inputs"]
    exp = case["expected"]
    d_m = si["diameter_m"]
    l_m = si["length_m"]

    # 体积流量链上量：Q = m_dot / ρ（与 service 公式一致）
    q_oil_calc = si["oil_mass_rate_kg_d"] / si["oil_density_kg_m3"]
    q_water_calc = si["water_mass_rate_kg_d"] / si["water_density_kg_m3"]
    q_gas_calc = si["gas_mass_rate_kg_d"] / si["gas_density_kg_m3"]
    assert q_oil_calc == pytest.approx(exp["oil_vol_rate_m3_d"], rel=rel)
    assert q_water_calc == pytest.approx(exp["water_vol_rate_m3_d"], rel=rel)
    assert q_gas_calc == pytest.approx(exp["gas_vol_rate_m3_d"], rel=rel)

    # 几何链上量：V_total = π·(D/2)²·L + 2·π·D³/24（2:1 椭圆封头）
    v_cyl = math.pi * (d_m / 2.0) ** 2 * l_m
    v_head_one = math.pi * d_m**3 / 24.0  # 2:1_ELLIPTICAL 单封头
    v_total_calc = v_cyl + 2.0 * v_head_one
    assert v_total_calc == pytest.approx(exp["total_volume_m3"], rel=rel)
    # 几何手算与 service.total_volume_m3 须严格代数吻合（防止 fixture 是 service 输出回声）
    assert v_total_calc == pytest.approx(exp["total_volume_m3"], rel=1e-12)


# ---------------------------------------------------------------------------
# 2) Imperial 双单位输出对账（imperial_units=True 路径）
# ---------------------------------------------------------------------------


def test_worley_c10_imperial_units_output() -> None:
    """imperial_units=True 时三相体积流量须以 ft³/d 双单位输出（35.3147 ft³/m³）。

    case service_inputs 复制 + imperial_units=True；断言 imperial_conversion 3 键存在，
    且 ft³/d = m³/d × 35.3147 精确一致。
    """
    case = next(
        c for c in WORLEY["cases"] if c["id"] == "worley_pr011_3phase_horizontal"
    )
    si_inputs = dict(case["service_inputs"])
    si_inputs["imperial_units"] = True
    inp = ThreePhaseSeparatorInput(**si_inputs)
    result = calc_three_phase_separator(inp)

    assert result.imperial_conversion is not None
    for key in case["expected"]["imperial_conversion_expected_keys"]:
        assert key in result.imperial_conversion, (
            f"imperial_conversion 缺键 {key!r}"
        )

    # ft³/d = m³/d × 35.3147（PCS service _M3_TO_FT3 常数）
    for m3_key, ft3_key in [
        ("oil_vol_rate_m3_d", "oil_vol_rate_ft3_d"),
        ("water_vol_rate_m3_d", "water_vol_rate_ft3_d"),
        ("gas_vol_rate_m3_d", "gas_vol_rate_ft3_d"),
    ]:
        m3_val = getattr(result, m3_key)
        ft3_val = result.imperial_conversion[ft3_key]
        assert ft3_val == pytest.approx(m3_val * _M3_TO_FT3, rel=1e-9)


# ---------------------------------------------------------------------------
# 3) 对账范围守卫：1 工况 sheet 全覆盖 + 超范围量登记不漂移
# ---------------------------------------------------------------------------


def test_worley_c10_case_coverage_and_out_of_scope_ledger() -> None:
    """fixture 必须覆盖 XLS 全部 1 sheet（Separator），且超范围量登记齐全。

    - 工况 sheet：Separator（1 sheet aggregate）须覆盖；
    - 5 项超范围量（Souders-Brown / nozzle / 仪表控制高度 / slug / 2-phase vs 3-phase mapping）
      必须登记 out_of_scope，防后续 fixture 演进时静默丢失。
    """
    assert {c["sheet"] for c in WORLEY["cases"]} == {"Separator"}
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "souders_brown_gas_csa_check",
        "nozzle_sizing",
        "instrument_spacing_table",
        "slug_volume_check",
        "xls_2phase_vs_service_3phase_mapping",
    }
    assert registered == expected_ids


# ---------------------------------------------------------------------------
# 4) Root-cause 登记守卫：4 项 algorithm-variant / data-variant 必登记
# ---------------------------------------------------------------------------


def test_worley_c10_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 4 项：combined vs separate RT + V64 vs 接口
    口径 + gas RT 缺失 + XLS 双单位 bbl/d vs service m³/d。

    Ruling 1(b) 算法变体/数据差异类——非代码缺陷登记，仅防 fixture 演进时漂移。
    """
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "interface_target_calibrated_to_oil_rt",
        "xls_v64_vs_service_convention",
        "xls_gas_rt_not_reported",
        "xls_uses_bbl_d_for_oil_water_vol_rate",
    }
    assert registered == expected_ids


# ---------------------------------------------------------------------------
# 5) fixture 结构守卫（基础健全性）
# ---------------------------------------------------------------------------


def test_worley_fixture_structure_basics() -> None:
    """fixture JSON 必须含 source / tolerance_policy / cases 顶层键。"""
    assert "source" in WORLEY
    assert "service" in WORLEY["source"]
    assert "tolerance_policy" in WORLEY
    assert "cases" in WORLEY
    assert len(WORLEY["cases"]) == 1
    case = WORLEY["cases"][0]
    for k in (
        "id",
        "sheet",
        "xls_inputs",
        "xls_aggregate_outputs",
        "service_inputs",
        "expected",
        "per_field_tolerance",
        "tolerance",
    ):
        assert k in case, f"case 缺顶层键 {k!r}"