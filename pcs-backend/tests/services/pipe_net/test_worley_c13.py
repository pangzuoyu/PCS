"""P6-6A Task 6 + P6-6B T3：C-13 PIPE_NET 浪涌压力 vs Worley 真实算例 WS-CA-PR-014 对账测试。

数据源：sample/Process caculation from Worley/…/WS-CA-PR-014 .xls（gitignored 只读）；
提取 dump：.superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-014.json
fixture：tests/services/pipe_net/fixtures/worley_c13_surge_pressure.json
（含 Worley 原始输入 cell 坐标、单位换算链、容差分级与放宽/收紧理由）

对账范围：
1. 单工况 sheet 对账（PIPELINE SURGE PRESSURE）：wave_speed_m_s（Wylie-Streeter 含管壁修正）
   + surge_pressure_pa（Joukowsky 1898）+ critical_close_time_s（MOC 边界）
   + is_joukowsky_applicable 布尔 + formula_ref 完整性 + imperial_conversion 键位（None）。
2. XLS-tautology 独立手算：Wylie-Streeter 公式以 XLS L24 E=207e9 重算，验证
   wave_speed_m_s ≈ 1302.4134 m/s（XLS L31，rel=0）+ surge_pressure_pa ≈ 2517868 Pa
   （XLS L33，rel=0），独立证明 XLS 公式解释正确（与 service 实现同构，仅 E 取值不同）。
3. 几何/流速链上量独立复算：v = Q/(π·D²/4)/3600（XLS L30 派生链）。

SPEC §5 分级：C-13 强公式 0.1%（rel≤1e-3）；P6-6B T3 起 PCS service pipe_material
枚举走 pipe_e_modulus CONFIG 表（API 5L X42/X52/X65/X70/X80 + ASTM A106/A335
共 8 项管材等级）；fixture pipe_material='X65'（API 5L X65 = 30e6 psi = 206.8428 GPa）
与 XLS L24 E=207 GPa 差 ≈ 0.076%，恢复 SPEC §5 强公式 1e-3 标准档（不再放宽）。

处置结论：P6-6A 阶段通过，root_cause_notes 登记 1 项工程化圆整差异闭环
（E modulus 207 vs X65 206.8428 → 闭环至 P6-6B T3 pipe_e_modulus 表）+ v 派生口径 +
out_of_scope 5 项（XLS 慢关阀 d/25 check / Table 1 流体物性 / Table 2 材料物性 /
imperial 显示 / config 1/3 锚固选项）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services._compound_config_cache import (
    clear_all_caches,
    get_pipe_E_modulus_table,
)
from app.services.pipe_net.surge_pressure import (
    SurgePressureInput,
    calc_water_hammer_surge,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c13_surge_pressure.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))

# Wylie-Streeter / Joukowsky 公式常数：
# P6-6B T3 起 PCS service 走 pipe_e_modulus CONFIG 表（API 5L X65 = 30e6 psi
# = 206.8428 GPa 工程圆整值）；fixture.service_inputs.pipe_material='X65'。
_E_PCS_X65 = 30_000_000 * 6894.76  # 206.8428e9 Pa
_E_XLS_PR_014 = 207e9  # Worley XLS L24 取 Table 2 Steel 范围 200-210 GN/m² 的中段值
_C1_ANCHORED_BOTH = 0.91  # XLS AF26 = 1 - 0.3²


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) 单工况 sheet 全量对账（fixture 参数化）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_worley_c13_case_reconciliation(case_id: str) -> None:
    """单工况对账：Wylie-Streeter + Joukowsky + MOC 临界关阀 + formula_ref。

    断言覆盖 XLS PIPELINE SURGE PRESSURE sheet 全部本模块契约内输出量：
    wave_speed_m_s / surge_pressure_pa / critical_close_time_s /
    is_joukowsky_applicable / formula_ref 完整性 / imperial_conversion 键位。
    Per-field tolerance 见 fixture.per_field_tolerance；P6-6B T3 起恢复 SPEC §5
    强公式 1e-3 标准档（X65 与 XLS E 差 ≈ 0.076%）。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    per_field = case["per_field_tolerance"]
    expected = case["expected"]

    result = calc_water_hammer_surge(SurgePressureInput(**case["service_inputs"]))

    # 数值字段逐项断言（per_field_tolerance 覆盖默认 rel）
    for key, rel_info in per_field.items():
        if rel_info["rel"] is None:
            continue  # 跳过布尔/字段完整性（独立断言）
        rel = rel_info["rel"]
        if key not in expected:
            continue
        actual = getattr(result, key)
        exp = expected[key]
        assert actual == pytest.approx(exp, rel=rel), (
            f"{case_id}.{key}: PCS={actual!r} vs expected={exp!r}（rel 门槛 {rel}）"
        )

    # 布尔字段：is_joukowsky_applicable（XLS ts < tc → True；PCS ts=1.0 < tc_pcs=1.0504 → True）
    assert result.is_joukowsky_applicable is expected["is_joukowsky_applicable"], (
        f"{case_id}: is_joukowsky_applicable={result.is_joukowsky_applicable}，"
        f"XLS 推断={expected['is_joukowsky_applicable']}"
    )

    # formula_ref 完整性（必须含 3 公式键：wave_speed / joukowsky / critical_close_time）
    for k in expected["formula_ref_expected_keys"]:
        assert k in result.formula_ref, f"{case_id}: formula_ref 缺键 {k!r}"

    # imperial_units=False → imperial_conversion 必须 None
    assert result.imperial_conversion is None, (
        f"{case_id}: imperial_units=False 时 imperial_conversion 应为 None，"
        f"实际={result.imperial_conversion!r}"
    )


# ---------------------------------------------------------------------------
# 2) Wylie-Streeter 公式独立手算（XLS-tautology）—— 证明 XLS 公式解释正确
# ---------------------------------------------------------------------------


def test_wylie_streeter_xls_formula_reproduces_l31_exactly() -> None:
    """Wylie-Streeter 公式（E_xls=207e9）独立手算复现 XLS L31=1302.4134 m/s。

    不调用 service；以 XLS 物理量手算 a_f = √(K/ρ)，再走 Wylie-Streeter 含管壁修正
    a = a_f / √(1 + (K·D)/(E·e)·C₁)，应 = XLS L31 原值（rel<1e-12）。证明 XLS 公式
    解释正确（与 service 实现同构），E 取值差是工程化圆整而非代码缺陷。
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    rho = si["fluid_density_kg_m3"]
    K = si["fluid_bulk_modulus_pa"]
    D = si["pipe_diameter_m"]
    e_wall = si["wall_thickness_m"]
    v = si["flow_velocity_m_s"]
    E = _E_XLS_PR_014
    C1 = _C1_ANCHORED_BOTH

    # 纯流体声速
    a_fluid = math.sqrt(K / rho)
    # Wylie-Streeter 含管壁修正
    correction = (K * D / (E * e_wall)) * C1
    a_xls = a_fluid / math.sqrt(1.0 + correction)
    # Joukowsky 浪涌压力
    pi_xls = rho * a_xls * v

    xls_expected_wave = case["xls_tautology_expected"]["wave_speed_m_s_with_xls_e"]
    xls_expected_pi = case["xls_tautology_expected"]["surge_pressure_pa_with_xls_e"]

    # 与 XLS L31/L33 全精度逐位一致（rel<1e-12，独立验证 XLS 公式解释）
    assert a_xls == pytest.approx(xls_expected_wave, rel=1e-12), (
        f"Wylie-Streeter 手算 a_xls={a_xls!r} ≠ XLS L31={xls_expected_wave!r}"
    )
    assert pi_xls == pytest.approx(xls_expected_pi, rel=1e-12), (
        f"Joukowsky 手算 Pi_xls={pi_xls!r} ≠ XLS L33={xls_expected_pi!r}（Pa）"
    )


def test_service_uses_pcs_x65_via_db_cache() -> None:
    """验证 service 走 pipe_e_modulus CONFIG 表读 X65=30e6 psi=206.8428 GPa。

    P6-6B T3 起 PCS service pipe_material='X65' 由 get_pipe_E_modulus_table()
    5 min TTL 缓存加载（DB 不可达时 fallback 到内联 5 等级 X42~X80 圆整值，
    X65=30e6 psi=206.8428e9 与 DB 行一致）；与 Wylie-Streeter 手算（E_xls=207e9）
    的 rel 差应 ≈ 8.7e-5（即 fixture.xls_tautology_expected.wave_speed_rel_diff_xls_e_vs_pcs_e），
    证明：
    - service 用的是 30e6 psi = 206.8428 GPa（不是 207e9 XLS 取值）；
    - 与 XLS E 的差异由 pipe_e_modulus CONFIG 表（工艺室签字）+ XLS 圆整口径共同决定。

    容差断言 0 < rel_diff < 1.5e-4（覆盖数值精度边界）。
    """
    clear_all_caches()  # 确保不命中陈旧 TTL 缓存
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    # 验证 service 实际加载 X65（DB 优先；DB 不可达时 fallback 内联常量，
    # 两者 X65=30e6 psi=206.8428e9 一致）
    e_table = get_pipe_E_modulus_table()
    if e_table is None:
        # DB 不可达时 service fallback 内联 5 等级；测试仍走 service 入口，
        # 由 fallback 常量覆盖。无需 assert db_table（不依赖 DB 路径）。
        pass
    else:
        assert "X65" in e_table, f"pipe_e_modulus 缺 X65 行：{sorted(e_table.keys())}"
        assert e_table["X65"] == pytest.approx(_E_PCS_X65, rel=1e-9), (
            f"X65 E 模量 {e_table['X65']!r} ≠ 预期 {_E_PCS_X65!r}"
            f"（30e6 psi 工程圆整）"
        )

    result = calc_water_hammer_surge(SurgePressureInput(**si))

    rho = si["fluid_density_kg_m3"]
    K = si["fluid_bulk_modulus_pa"]
    D = si["pipe_diameter_m"]
    e_wall = si["wall_thickness_m"]
    a_fluid = math.sqrt(K / rho)

    # E=207e9 时的 Wylie-Streeter 手算
    correction_xls = (K * D / (_E_XLS_PR_014 * e_wall)) * _C1_ANCHORED_BOTH
    a_xls = a_fluid / math.sqrt(1.0 + correction_xls)

    rel_diff = (a_xls - result.wave_speed_m_s) / a_xls
    # service 用 X65=206.8428 GPa（小于 XLS 207 GPa）→ service a 偏小 → rel_diff > 0
    expected_rel = case["xls_tautology_expected"]["wave_speed_rel_diff_xls_e_vs_pcs_e"]
    assert rel_diff == pytest.approx(expected_rel, rel=1e-2), (
        f"实测 rel_diff={rel_diff!r} ≠ 预期 {expected_rel!r}"
        f"（E=207e9 vs X65=206.8428e9 偏差）"
    )
    # 工程化圆整数量级（~0.01%）：应落在 0 ~ 1.5e-4 区间
    assert 0 < rel_diff < 1.5e-4, (
        f"rel_diff={rel_diff!r} 越出 [0, 1.5e-4] 工程化圆整数量级窗口"
    )


# ---------------------------------------------------------------------------
# 3) 流速派生链独立复算（v = Q / (π·D²/4) / 3600）
# ---------------------------------------------------------------------------


def test_velocity_derivation_from_q_and_d() -> None:
    """XLS L30 v=1.9371067997122686 由 Q=1008 m³/hr + D=429 mm 派生。

    独立复算 v = Q/(π·D²/4)/3600；XLS 完整保留 17 位精度，rel<1e-12 严格一致。
    防 fixture.service_inputs.flow_velocity_m_s 非 XLS 原值（口径/单位漂移）。
    """
    case = WORLEY["cases"][0]
    xls_q_m3_per_hr = case["xls_inputs"]["L17_m3_per_hr"]["value"]
    xls_d_mm = case["xls_inputs"]["AF14_mm"]["value"]
    xls_v = case["xls_inputs"]["L30_derived_v_m_s"]["value"]

    d_m = xls_d_mm * 0.001
    a_pipe = math.pi * d_m**2 / 4.0
    v_calc = xls_q_m3_per_hr / a_pipe / 3600.0

    assert v_calc == pytest.approx(xls_v, rel=1e-12), (
        f"v 派生 v_calc={v_calc!r} ≠ XLS L30={xls_v!r}（Q={xls_q_m3_per_hr}, D={d_m}）"
    )
    # service 入参须与 XLS L30 全精度一致（bit-for-bit，避免传递值非原值）
    assert case["service_inputs"]["flow_velocity_m_s"] == pytest.approx(xls_v, rel=1e-15)


# ---------------------------------------------------------------------------
# 4) 对账范围守卫：1 工况 sheet 全覆盖 + 超范围量登记不漂移
# ---------------------------------------------------------------------------


def test_worley_c13_case_coverage_and_out_of_scope_ledger() -> None:
    """fixture 必须覆盖 XLS 全部 1 sheet（PIPELINE SURGE PRESSURE），且超范围量登记齐全。

    - 工况 sheet：PIPELINE SURGE PRESSURE（1 sheet aggregate）须覆盖；
    - 5 项超范围量（slow_closure_moc_check / table_1_liquid_properties /
      table_2_material_properties / imperial_unit_display / config_options_1_3）
      必须登记 out_of_scope，防后续 fixture 演进时静默丢失。
    """
    assert {c["sheet"] for c in WORLEY["cases"]} == {"PIPELINE SURGE PRESSURE"}
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_slow_closure_moc_check",
        "xls_table_1_liquid_properties",
        "xls_table_2_material_properties",
        "xls_imperial_unit_display",
        "xls_config_options_1_3",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符：已登记 {registered}，预期 {expected_ids}"
    )


# ---------------------------------------------------------------------------
# 5) Root-cause 登记守卫：E modulus mismatch + v 派生口径必登记
# ---------------------------------------------------------------------------


def test_worley_c13_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 2 项：E modulus X65 闭环 + v 派生口径。

    P6-6B T3 起 E modulus mismatch 已闭环（pipe_e_modulus CONFIG 表，X65=206.8428 GPa
    替代 CARBON_STEEL=200e9 硬编码），root_cause_notes 改登记闭环事实；
    v 派生口径维持原状。
    """
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "E_modulus_x65_xls_match",
        "xls_v_derivation",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符：已登记 {registered}，预期 {expected_ids}"
    )


# ---------------------------------------------------------------------------
# 6) fixture 结构守卫（基础健全性）
# ---------------------------------------------------------------------------


def test_worley_c13_fixture_structure_basics() -> None:
    """fixture JSON 顶层键健全性：source/tolerance_policy/cases/root_cause/out_of_scope。"""
    for k in ("source", "tolerance_policy", "cases", "root_cause_notes", "out_of_scope"):
        assert k in WORLEY, f"fixture 缺顶层键 {k!r}"
    assert "service" in WORLEY["source"]
    assert len(WORLEY["cases"]) == 1
    case = WORLEY["cases"][0]
    for k in (
        "id",
        "sheet",
        "xls_inputs",
        "xls_aggregate_outputs",
        "service_inputs",
        "expected",
        "xls_tautology_expected",
        "per_field_tolerance",
        "tolerance",
    ):
        assert k in case, f"case 缺顶层键 {k!r}"