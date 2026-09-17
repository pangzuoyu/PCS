"""P5-3 PSV 安全阀模块。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §265-417 实施 6 task：
- P5-3-1 fire_case_service（API 521 7th + GB/T 150.1 2011/2024 双路径）
- P5-3-2 other_cases_service（阀门关闭 + 反应失控 + 热膨胀）
- P5-3-3 relief_aggregator_service（多工况叠加）
- P5-3-4 relief_area_service（API 520 + GB/T 12241 双路径）
- P5-3-5 orifice_service + breathing_valve_service
- P5-3-6 psv_persist + API + outlet_stream

API/GB 计算逻辑完全隔离（SUP-P5-PSV-001 §4.1）：各自独立函数 + 公用入口分发。
"""
from app.services.psv.fire_case_service import (
    FireCaseFormulaRef,
    FireCaseInput,
    FireCaseResult,
    calc_fire_case,
    calc_fire_case_api521,
    calc_fire_case_gb150_v2011,
    calc_fire_case_gb150_v2024,
)
from app.services.psv.other_cases_service import (
    ClosedValveInput,
    ClosedValveResult,
    OtherCaseFormulaRef,
    ReactionRunawayInput,
    ReactionRunawayResult,
    ThermalExpansionInput,
    ThermalExpansionResult,
    calc_closed_valve_case,
    calc_reaction_runaway_case,
    calc_thermal_expansion_case,
)

__all__ = [
    "FireCaseInput",
    "FireCaseResult",
    "FireCaseFormulaRef",
    "calc_fire_case",
    "calc_fire_case_api521",
    "calc_fire_case_gb150_v2011",
    "calc_fire_case_gb150_v2024",
    "ClosedValveInput",
    "ClosedValveResult",
    "ReactionRunawayInput",
    "ReactionRunawayResult",
    "ThermalExpansionInput",
    "ThermalExpansionResult",
    "OtherCaseFormulaRef",
    "calc_closed_valve_case",
    "calc_reaction_runaway_case",
    "calc_thermal_expansion_case",
]