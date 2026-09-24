"""P6-FLR 火炬系统 FLARE_SYS 模块。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4 / §5.15.3 / §5.15.5 实施
项目级多 PSV 泄放叠加、火炬总管 Mach 数法尺寸计算，以及 KOD 与水封液柱
综合计算：

- ``relief_aggregator`` 提供 ``aggregate_flare_load``：从 ``relief_results``
  按 ``project_id`` + ``standard_profile_code`` 聚合，按主导工况（每 PSV
  max required_relief_area 对应 scenario）跨 PSV 求和，输出
  ``FlareLoad``（per_scenario_total / per_psv_dominant / total）。
- ``header_sizing`` 提供 ``calc_header_sizing``：按 API 521 §5.15.4
  Mach 数法 + 等温可压缩管流反求总管直径 D（不依赖 DB；纯计算函数）。
- ``kod_sizing`` 提供 ``calc_kod_sizing``：按 API 521 §5.15.3
  Souders-Brown 法计算 KOD 直径 + §5.15.5 Water Seal 液柱高度综合
  （不依赖 DB；纯计算函数）。
- ``stack_design`` 提供 ``calc_stack_design``：按 API 521 §7.4.2.2
  Stack Height（Pasquill-Gifford 修正）+ §7.4.2.3 Thermal Radiation
  （点源模型）+ BEDD 限值校验综合（不依赖 DB；纯计算函数）。

粒度从「单 PSV 多工况保守 max」（P5-3-3 ``psv/relief_aggregator_service``
``calc_relief_aggregate``）升级到「项目级多 PSV 叠加」+「总管尺寸」
+「KOD + 水封」+「火炬高度与辐射」。五模块独立、不互相调用；FLARE_SYS
不下沉到 ``app/services/psv/`` 子树（避免 PSV 选型与 FLARE 网络拓扑耦合）。
"""
from __future__ import annotations

from app.services.exceptions import FlareAggregatorInputError
from app.services.flare.header_sizing import (
    HeaderSizingInput,
    HeaderSizingInputError,
    HeaderSizingResult,
    calc_header_sizing,
)
from app.services.flare.kod_sizing import (  # P6-2 Task 21
    KodInput,
    KodResult,
    KodSizingInputError,
    KodSizingResult,
    WaterSealInput,
    WaterSealInputError,
    WaterSealResult,
    calc_kod,
    calc_kod_sizing,
    calc_water_seal,
)
from app.services.flare.relief_aggregator import (
    FlareLoad,
    FlarePsvContribution,
    Scenario,
    aggregate_flare_load,
)
from app.services.flare.stack_design import (  # P6-2 Task 22
    RadiationCheckInput,
    RadiationCheckInputError,
    RadiationCheckResult,
    StackDesignResult,
    StackHeightInput,
    StackHeightInputError,
    StackHeightResult,
    calc_radiation_check,
    calc_stack_design,
    calc_stack_height,
)

__all__ = [
    "Scenario",
    "FlareLoad",
    "FlarePsvContribution",
    "FlareAggregatorInputError",
    "aggregate_flare_load",
    # P6-2 Task 20 — header_sizing（Mach 数法 + 等温可压缩管流）
    "HeaderSizingInput",
    "HeaderSizingResult",
    "HeaderSizingInputError",
    "calc_header_sizing",
    # P6-2 Task 21 — kod_sizing（Souders-Brown + Water Seal 液柱）
    "KodInput",
    "KodResult",
    "WaterSealInput",
    "WaterSealResult",
    "KodSizingResult",
    "KodSizingInputError",
    "WaterSealInputError",
    "calc_kod",
    "calc_water_seal",
    "calc_kod_sizing",
    # P6-2 Task 22 — stack_design（Stack Height + Thermal Radiation + BEDD）
    "StackHeightInput",
    "StackHeightResult",
    "RadiationCheckInput",
    "RadiationCheckResult",
    "StackDesignResult",
    "StackHeightInputError",
    "RadiationCheckInputError",
    "calc_stack_height",
    "calc_radiation_check",
    "calc_stack_design",
]