"""P6-6A Task 4：C-09 AS 2360.1.1 Limit 校核 vs Worley 真实算例 WS-CA-PR-007 对账测试。

数据源：sample/Process caculation from Worley/…/WS-CA-PR-007.xls（gitignored 只读）；
提取 dump：.superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-007.json
fixture：tests/services/cv/fixtures/worley_c09_as2360_limit.json
（含 Worley 原始输入 cell 坐标、英制→SI 换算链、容差分级与收紧理由）

对账范围（Ruling 3：XLS-PR-007 = sizing, 非 limit）：
1. 3 cases（SI Case I / SI Case J/K / Imp Case）— sonic velocity m/s 与 XLS r44 对账；
2. d limit check（XLS r39/r40 给定 orifice d_orifice < 25.4mm → service is_limit_applicable=True）。

超出模块契约的 XLS 输出（b/Cd/e/ReD/Dw/max_velocity/L1/L2/sizing limits checklist）
登记于 fixture out_of_scope，coverage test 守卫登记不漂移。

SPEC §5 分级：C-09 经验拟合级 rel≤1e-2；本批各 case 在门槛内收紧至 1e-3
（SI 双 case bit-for-bit 0 偏差，Imp case 受换算链累积 ≤7.6e-7）。
处置结论：全部通过，零 Ruling 1 代码修复。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.cv.as_2360_1_1_service import (
    As2360LimitInput,
    calc_as_2360_1_1_limit,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c09_as2360_limit.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ---------------------------------------------------------------------------
# 1) 三工况 sheet 全量对账（fixture 参数化）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _case_ids())
def test_worley_c09_case_reconciliation(case_id: str) -> None:
    """单工况对账：sonic_velocity_m_s + is_limit_applicable + formula_ref 非空。

    Ruling 3 收窄对账范围至 sonic velocity + d limit check（仅 AS 2360.1.1
    service 主函数 calc_as_2360_1_1_limit 与 XLS sizing 表的算法族直接交叠）；
    其余 XLS sizing 输出（b/Cd/e/ReD/Dw/max_velocity 等）登记 out_of_scope 不 assert。
    """
    case = next(c for c in WORLEY["cases"] if c["id"] == case_id)
    rel = case["tolerance"]["rel"]

    result = calc_as_2360_1_1_limit(
        As2360LimitInput(**case["service_inputs"])
    )

    expected = case["expected"]

    # sonic_velocity_m_s：a = √(γ·P₁/ρ)，是 XLS r44 与 service 直接交叠量
    assert result.sonic_velocity_m_s == pytest.approx(
        expected["sonic_velocity_m_s"], rel=rel
    ), (
        f"{case_id}: sonic_velocity_m_s={result.sonic_velocity_m_s!r} "
        f"vs XLS={expected['sonic_velocity_m_s']!r}（rel 门槛 {rel}）"
    )

    # is_limit_applicable：d < 1in 触发；XLS r39/r40 给的 orifice d_orifice 均 < 25.4mm
    assert result.is_limit_applicable is expected["is_limit_applicable"], (
        f"{case_id}: is_limit_applicable={result.is_limit_applicable} "
        f"vs XLS 推断={expected['is_limit_applicable']}（d_orifice < 25.4mm 应触发）"
    )

    # is_choked + actual_pressure_ratio：链上交叉验证（不在主断言容差门槛内
    # 但作为 fixture 完整性检查，必与 XLS r32 一致）
    assert result.is_choked is expected["is_choked"], (
        f"{case_id}: is_choked={result.is_choked} "
        f"vs 推断={expected['is_choked']}"
    )
    assert result.actual_pressure_ratio == pytest.approx(
        expected["actual_pressure_ratio"], rel=1e-6
    ), (
        f"{case_id}: actual_pressure_ratio={result.actual_pressure_ratio} "
        f"vs XLS r32={expected['actual_pressure_ratio']}"
    )

    # formula_ref 非空：service 必须含 4 个公式溯源键（SPEC §3.7.1）
    assert "sonic_velocity" in result.formula_ref
    assert "critical_pressure_ratio" in result.formula_ref
    assert "limit_threshold" in result.formula_ref
    assert "as_standard" in result.formula_ref


# ---------------------------------------------------------------------------
# 2) 对账范围守卫：fixture 完整性 + out_of_scope 登记不漂移
# ---------------------------------------------------------------------------


def test_worley_c09_fixture_coverage_and_out_of_scope_ledger() -> None:
    """fixture 必须覆盖 XLS 含 AS 2360.1.1 算例的 sheet，且超范围量登记齐全。

    - 工况 sheet：SI（Case I + J/K 2 cases）+ Imp（1 case）共 3 cases；
    - SI sizing outputs（b/Cd/e/ReD/Dw/max_velocity/L1/L2/Limits checklist）
      全部 out_of_scope，逐项登记，防后续 fixture 演进时静默丢失。
    """
    assert {c["sheet"] for c in WORLEY["cases"]} == {"SI", "Imp"}
    assert {c["id"] for c in WORLEY["cases"]} == {
        "si_case_1",
        "si_case_jk",
        "imp_case",
    }
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    assert registered == {
        "beta_ratio_b",
        "expansion_factor_e",
        "reynolds_number_ReD",
        "discharge_coefficient_C",
        "pressure_loss_Dw",
        "max_velocity",
        "relative_tapping_L1_L2",
        "as2360_sizing_limits_checklist",
        "xls_input_artifact",
        "imp_j_k_column_duplication",
    }


def test_worley_c09_ruling_3_recorded() -> None:
    """Ruling 3（XLS-PR-007 = sizing, 非 limit）+ plan mapping defect 必须登记。"""
    root_cause_ids = {n["id"] for n in WORLEY["root_cause_notes"]}
    assert "xls_is_sizing_not_limit" in root_cause_ids
    assert "plan_mapping_defect" in root_cause_ids