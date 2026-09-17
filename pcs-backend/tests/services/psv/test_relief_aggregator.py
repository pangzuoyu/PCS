"""P5-3-3 PSV 多工况叠加聚合测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §319-343 + API 521 7th Ed. §5.15.4：
- 多工况同时考虑 → 取 max W_mass（保守原则）
- 不做加和（避免重复保守）
- 主导工况识别用于 SPEC 报告 / audit
"""
from __future__ import annotations

import pytest

from app.services.psv import (
    ReliefAggregateInput,
    ReliefCase,  # noqa: E501
    calc_relief_aggregate,
)
from app.services.psv.fire_case_service import FireCaseFormulaRef
from app.services.psv.other_cases_service import OtherCaseFormulaRef
from app.services.psv.relief_aggregator_service import PsvAggregateInputError

_FIRE_REF = FireCaseFormulaRef(standard="API_521", version="7th", clause="§5.15.2.2.1")
_CLOSED_VALVE_REF = OtherCaseFormulaRef(standard="API_521", version="7th", clause="§5.15.2.3")
_REACTION_REF = OtherCaseFormulaRef(standard="API_521", version="7th", clause="§5.15.2.4")
_THERMAL_REF = OtherCaseFormulaRef(standard="API_521", version="7th", clause="§5.15.2.5")


# ============================================================================
# 1. 单工况（4 scenario 各 1 例）
# ============================================================================


@pytest.mark.parametrize("scenario", ["FIRE", "CLOSED_VALVE", "REACTION_RUNAWAY", "THERMAL_EXPANSION"])  # noqa: E501
def test_single_case_dominant_is_self(scenario):
    """单工况：主导 = self，max W_mass = 自身 W_mass。"""
    case = ReliefCase(
        scenario=scenario,  # type: ignore[arg-type]
        relief_mass_flow_kgs=1.5,
        relief_volume_flow_m3s=1.25,
        formula_ref=_FIRE_REF,
    )
    inp = ReliefAggregateInput(cases=(case,))
    r = calc_relief_aggregate(inp)

    assert r.max_relief_mass_flow_kgs == 1.5
    assert r.max_relief_volume_flow_m3s == 1.25
    assert r.dominant_scenario == scenario
    assert r.case_count == 1
    assert r.cases == (case,)


# ============================================================================
# 2. 多工况取 max（核心断言）
# ============================================================================


def test_multi_case_takes_max_W_mass():
    """多工况：取最大 W_mass（保守原则）。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=5.0, relief_volume_flow_m3s=4.0, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("CLOSED_VALVE", relief_mass_flow_kgs=1.2, relief_volume_flow_m3s=1.0, formula_ref=_CLOSED_VALVE_REF),  # noqa: E501
        ReliefCase("REACTION_RUNAWAY", relief_mass_flow_kgs=3.5, relief_volume_flow_m3s=2.8, formula_ref=_REACTION_REF),  # noqa: E501
        ReliefCase("THERMAL_EXPANSION", relief_mass_flow_kgs=0.5, relief_volume_flow_m3s=0.4, formula_ref=_THERMAL_REF),  # noqa: E501
    )
    inp = ReliefAggregateInput(cases=cases)
    r = calc_relief_aggregate(inp)

    # FIRE 最大 (5.0)
    assert r.max_relief_mass_flow_kgs == 5.0
    assert r.max_relief_volume_flow_m3s == 4.0
    assert r.dominant_scenario == "FIRE"
    assert r.case_count == 4


def test_no_summation():
    """保守原则：不加和 W_mass；总和 vs max 必须严格不等（W_mass > 0 时）。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=5.0, relief_volume_flow_m3s=4.0, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("CLOSED_VALVE", relief_mass_flow_kgs=1.2, relief_volume_flow_m3s=1.0, formula_ref=_CLOSED_VALVE_REF),  # noqa: E501
    )
    inp = ReliefAggregateInput(cases=cases)
    r = calc_relief_aggregate(inp)

    sum_W = 5.0 + 1.2
    assert r.max_relief_mass_flow_kgs == 5.0  # 取 max
    assert r.max_relief_mass_flow_kgs < sum_W  # 严格小于总和


# ============================================================================
# 3. 主导工况识别
# ============================================================================


def test_dominant_scenario_reaction_runaway():
    """主导工况识别：REACTION_RUNAWAY 最大。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=2.0, relief_volume_flow_m3s=1.5, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("REACTION_RUNAWAY", relief_mass_flow_kgs=10.0, relief_volume_flow_m3s=8.0, formula_ref=_REACTION_REF),  # noqa: E501
        ReliefCase("THERMAL_EXPANSION", relief_mass_flow_kgs=0.5, relief_volume_flow_m3s=0.4, formula_ref=_THERMAL_REF),  # noqa: E501
    )
    r = calc_relief_aggregate(ReliefAggregateInput(cases=cases))
    assert r.dominant_scenario == "REACTION_RUNAWAY"


def test_dominant_scenario_takes_first_max_on_tie():
    """并列 max：取首个（稳定排序）。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=5.0, relief_volume_flow_m3s=4.0, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("REACTION_RUNAWAY", relief_mass_flow_kgs=5.0, relief_volume_flow_m3s=4.0, formula_ref=_REACTION_REF),  # noqa: E501
    )
    r = calc_relief_aggregate(ReliefAggregateInput(cases=cases))
    # 并列时取首个 → FIRE
    assert r.dominant_scenario == "FIRE"


# ============================================================================
# 4. 边界异常
# ============================================================================


def test_empty_cases_raises():
    """cases 空 → PsvAggregateInputError。"""
    inp = ReliefAggregateInput(cases=())
    with pytest.raises(PsvAggregateInputError) as exc_info:
        calc_relief_aggregate(inp)
    assert "cases 列表为空" in str(exc_info.value)
    assert exc_info.value.code == "PSV_INPUT_ERROR"
    assert exc_info.value.status == 422


def test_negative_W_mass_raises():
    """relief_mass_flow_kgs < 0 → PsvAggregateInputError。"""
    case = ReliefCase(
        "FIRE",
        relief_mass_flow_kgs=-1.0,
        relief_volume_flow_m3s=0.0,
        formula_ref=_FIRE_REF,
    )
    with pytest.raises(PsvAggregateInputError) as exc_info:
        calc_relief_aggregate(ReliefAggregateInput(cases=(case,)))
    assert "不能为负" in str(exc_info.value)


# ============================================================================
# 5. 全 0 主导（边界 case）
# ============================================================================


def test_all_zero_dominant_is_first():
    """所有工况 W_mass = 0：max = 0，取首个。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=0.0, relief_volume_flow_m3s=0.0, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("CLOSED_VALVE", relief_mass_flow_kgs=0.0, relief_volume_flow_m3s=0.0, formula_ref=_CLOSED_VALVE_REF),  # noqa: E501
    )
    r = calc_relief_aggregate(ReliefAggregateInput(cases=cases))
    assert r.max_relief_mass_flow_kgs == 0.0
    assert r.dominant_scenario == "FIRE"


# ============================================================================
# 6. 透传 cases（audit 用）
# ============================================================================


def test_cases_transmitted_for_audit():
    """cases 完整透传，audit / SPEC 报告可遍历。"""
    cases = (
        ReliefCase("FIRE", relief_mass_flow_kgs=2.0, relief_volume_flow_m3s=1.5, formula_ref=_FIRE_REF),  # noqa: E501
        ReliefCase("REACTION_RUNAWAY", relief_mass_flow_kgs=10.0, relief_volume_flow_m3s=8.0, formula_ref=_REACTION_REF),  # noqa: E501
    )
    r = calc_relief_aggregate(ReliefAggregateInput(cases=cases))
    assert r.cases == cases
    assert len(r.cases) == 2