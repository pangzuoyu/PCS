"""P6-FLR 火炬系统 FLARE_SYS 模块。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4 实施项目级多 PSV 泄放叠加：

- ``relief_aggregator`` 提供 ``aggregate_flare_load``：从 ``relief_results``
  按 ``project_id`` + ``standard_profile_code`` 聚合，按主导工况（每 PSV
  max required_relief_area 对应 scenario）跨 PSV 求和，输出
  ``FlareLoad``（per_scenario_total / per_psv_dominant / total）。

粒度从「单 PSV 多工况保守 max」（P5-3-3 ``psv/relief_aggregator_service``
``calc_relief_aggregate``）升级到「项目级多 PSV 叠加」。两模块独立、不互
相调用；FLARE_SYS 不下沉到 ``app/services/psv/`` 子树（避免 PSV 选型与
FLARE 网络拓扑耦合）。
"""
from __future__ import annotations

from app.services.exceptions import FlareAggregatorInputError
from app.services.flare.relief_aggregator import (
    FlareLoad,
    FlarePsvContribution,
    Scenario,
    aggregate_flare_load,
)

__all__ = [
    "Scenario",
    "FlareLoad",
    "FlarePsvContribution",
    "FlareAggregatorInputError",
    "aggregate_flare_load",
]