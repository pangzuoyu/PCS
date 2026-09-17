"""P5-3-3 PSV 多工况叠加聚合。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §319-343 + API 521 7th Ed. §5.15.4：

多工况聚合原则（保守原则）：
- 多个工况同时考虑 → 取最大泄放量 W_mass（PSV 必须能覆盖最严苛工况）
- 不能简单加和（避免重复保守；保留 API 521 §5.15.4 规则）
- 主导工况识别用于 SPEC 报告与 audit

输入：
- ReliefCase（scenario 类别 + W_mass + Q_v + formula_ref）
- ReliefAggregateInput（cases 列表）

输出：
- ReliefAggregateResult（max W_mass + max Q_v + dominant_scenario + case_count + all_cases 透传）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.exceptions import PcsError


# ---------- 类型别名 ----------


Scenario = Literal[
    "FIRE",
    "CLOSED_VALVE",
    "REACTION_RUNAWAY",
    "THERMAL_EXPANSION",
]


@dataclass(frozen=True)
class ReliefCase:
    """单个泄放工况（P5-3-3 聚合单元）。

    字段：
      - scenario: 工况类别（4 种 Literal）
      - relief_mass_flow_kgs: 泄放质量流量 kg/s（来自 P5-3-1 / P5-3-2 子计算）
      - relief_volume_flow_m3s: 泄放体积流量 m³/s
      - formula_ref: 子工况公式溯源（P5-3-1 FireCaseFormulaRef 或 P5-3-2 OtherCaseFormulaRef）
    """

    scenario: Scenario
    relief_mass_flow_kgs: float
    relief_volume_flow_m3s: float
    formula_ref: object  # FireCaseFormulaRef | OtherCaseFormulaRef（接受两者）


@dataclass(frozen=True)
class ReliefAggregateInput:
    """多工况聚合输入。"""

    cases: tuple[ReliefCase, ...]


@dataclass(frozen=True)
class ReliefAggregateResult:
    """多工况聚合结果。

    字段：
      - max_relief_mass_flow_kgs: 最严苛工况的泄放质量流量（PSV 选型依据）
      - max_relief_volume_flow_m3s: 最严苛工况的泄放体积流量
      - dominant_scenario: 主导工况类别（max W_mass 对应的 scenario）
      - case_count: 输入工况数
      - cases: 透传所有工况（用于 audit / SPEC 报告）
    """

    max_relief_mass_flow_kgs: float
    max_relief_volume_flow_m3s: float
    dominant_scenario: Scenario
    case_count: int
    cases: tuple[ReliefCase, ...]


# ---------- 异常 ----------


class PsvAggregateInputError(PcsError):
    """PSV 多工况聚合输入不合法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 聚合实现 ----------


def calc_relief_aggregate(inp: ReliefAggregateInput) -> ReliefAggregateResult:
    """多工况叠加聚合（API 521 §5.15.4 保守原则）。

    取最大泄放质量流量 W_mass + 对应体积流量 + 主导工况。
    不做加和（避免重复保守）。
    """
    if not inp.cases:
        raise PsvAggregateInputError("cases 列表为空，至少需要 1 个工况")

    # 边界检查：每个 case 的 W_mass 必须 >= 0（0 表示该工况无贡献）
    for idx, case in enumerate(inp.cases):
        if case.relief_mass_flow_kgs < 0:
            raise PsvAggregateInputError(
                f"cases[{idx}].relief_mass_flow_kgs={case.relief_mass_flow_kgs} 不能为负"
            )
        if case.relief_volume_flow_m3s < 0:
            raise PsvAggregateInputError(
                f"cases[{idx}].relief_volume_flow_m3s="
                f"{case.relief_volume_flow_m3s} 不能为负"
            )

    # 取 max W_mass（保守原则）
    dominant_idx = 0
    max_W = inp.cases[0].relief_mass_flow_kgs
    for idx in range(1, len(inp.cases)):
        if inp.cases[idx].relief_mass_flow_kgs > max_W:
            max_W = inp.cases[idx].relief_mass_flow_kgs
            dominant_idx = idx

    dominant = inp.cases[dominant_idx]

    return ReliefAggregateResult(
        max_relief_mass_flow_kgs=max_W,
        max_relief_volume_flow_m3s=dominant.relief_volume_flow_m3s,
        dominant_scenario=dominant.scenario,
        case_count=len(inp.cases),
        cases=inp.cases,
    )


__all__ = [
    "Scenario",
    "ReliefCase",
    "ReliefAggregateInput",
    "ReliefAggregateResult",
    "calc_relief_aggregate",
    "PsvAggregateInputError",
]