"""FLARE_SYS 火炬系统泄放汇总（项目级，多 PSV 叠加）。

按 SPEC §3.2.3 P6-FLR-001 + API 521 §5.15.4 保守原则：

- 每个 PSV 在项目内可能有多条 ReliefResult（每个 scenario 一条）
- 每 PSV 取主导工况（max required_relief_area 对应 scenario）作为该 PSV 的贡献
- 跨 PSV 按主导工况分组求和（避免 N 个 PSV 全工况加和的过度保守）
- standard_profile_code 严格隔离（API_521 vs GB/T 不混合）

不对 P5-3-3 现有 ``relief_aggregator_service.calc_relief_aggregate`` 做扩展；
FLARE_SYS 独立模块（聚合粒度从「单 PSV」升级到「项目」）。

设计要点：

- ``aggregate_flare_load`` 接收 sync ``Session``（与 PSV 单工况聚合 service
  同源约定；上游 P5-3-6 persist 层使用 sync Session 模式）。
- ``per_scenario_total_cm2`` 与 ``dominant_scenario`` 用 ``str`` 而非
  ``ReliefScenario`` 枚举存储：字典键需可序列化（JSON dump 用），且枚举
  6 态中后 2 态（BLOCKED_OUTLET/COOLING_FAILURE/UPSET）不一定在 brief
  列出的 4 态 Literal 内，但实际数据仍按字符串聚合（数据契约兼容）。
- 默认 ``sign_status_filter=("CHECKED", "CHANGED")``：与 SUP-007 §3.1 9
  态门禁对齐，仅「已签审 / 已变更」记录计入（参照
  ``app/services/cia_engine.py:107`` 的 ``[CHECKED, CHANGED]`` 过滤
  模式）。

  > 注：brief 原案 ``("PENDING", "APPROVED")`` 与本仓 ``RecordSignStatus9``
  9 态枚举不对应（PENDING/APPROVED 在 RecordSignStatus9 中不存在；
  该值集合属 ConfigAsset 5 态枚举）。本服务面向 relief_results
  （RecordSignStatus9 9 态），改为 ``("CHECKED", "CHANGED")``，保持
  「仅有效记录计入」的语义不变；调用方可按需 override。
- ``selected_psv_id IS NULL`` 的 ReliefResult 视为未选型，不计入项目级
  火炬泄放（避免未完成选型的 PSV 触发虚假叠加）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calc import ReliefResult
from app.services.exceptions import FlareAggregatorInputError

# P5-3-3 已使用 4 态 Literal；本模块沿用 — 实际 dominant_scenario 取的是
# ReliefResult.relief_scenario 字段值，存为字符串（dict key 用）。枚举的
# 后 2 态（BLOCKED_OUTLET/COOLING_FAILURE/UPSET）超出 Literal 范围时会
# 通过 type ignore 规避（详见 _per_psv_dominant）。
Scenario = Literal["FIRE", "CLOSED_VALVE", "REACTION_RUNAWAY", "THERMAL_EXPANSION"]


@dataclass(frozen=True)
class FlarePsvContribution:
    """单个 PSV 对 FLARE_SYS 的贡献（audit 用）。

    字段：

    - psv_id: 选型 PSV 唯一标识（对应 ``relief_results.selected_psv_id``）
    - dominant_scenario: 主导工况（max required_relief_area 对应 ReliefResult 的
      ``relief_scenario`` 字段值）
    - required_relief_area_cm2: 主导工况对应的 ``required_relief_area``
      （单位 cm²，relief_results 字段已固定 cm²）
    - scenario_count: 该 PSV 在项目内有多少条 ReliefResult（max 候选基数）
    """

    psv_id: uuid.UUID
    dominant_scenario: str
    required_relief_area_cm2: float
    scenario_count: int


@dataclass(frozen=True)
class FlareLoad:
    """FLARE_SYS 项目级泄放汇总结果。

    字段：

    - project_id: 项目 UUID
    - standard_profile_code: 标准配置 code（API_521 / GB_T_150_1 / CUSTOM）
    - per_scenario_total_cm2: 各主导工况总泄放面积 cm²（跨 PSV 求和）
    - per_psv_dominant: 各 PSV 主导贡献明细（audit 用）
    - total_psv_count: 已计入的 PSV 数（去重后）
    - total_relief_area_cm2: 各 scenario 求和（=sum(per_scenario_total_cm2.values())）
    - sign_status_filter: 计入的 sign_status 集合（默认 CHECKED + CHANGED）
    """

    project_id: uuid.UUID
    standard_profile_code: str
    per_scenario_total_cm2: dict[str, float]
    per_psv_dominant: tuple[FlarePsvContribution, ...]
    total_psv_count: int
    total_relief_area_cm2: float
    sign_status_filter: tuple[str, ...] = ("CHECKED", "CHANGED")


def _per_psv_dominant(
    session: Session,
    project_id: uuid.UUID,
    standard_profile_code: str,
    sign_status_filter: tuple[str, ...],
) -> list[FlarePsvContribution]:
    """每 PSV 取主导工况（max required_relief_area）。

    按 ``relief_results`` 全表读 + Python 端分组 + max；刻意不做 SQL
    GROUP BY（避免跨 dialect 聚合 ``max() over JSONB 路径``）；

    返回 list（顺序 = 首次出现顺序），flavour 与 brief 对齐：
    每个 selected_psv_id 一条 FlarePsvContribution。

    实现细节：

    - ``required_relief_area IS NULL`` 视为 0 贡献（计算未完成的工况不计）
    - dominant_scenario 取 max 行的 ``relief_scenario.value``（枚举值字符串）
    """
    stmt = (
        select(ReliefResult)
        .where(
            ReliefResult.project_id == project_id,
            ReliefResult.standard_profile_code == standard_profile_code,
            ReliefResult.selected_psv_id.isnot(None),
            ReliefResult.sign_status.in_(sign_status_filter),
            ReliefResult.required_relief_area.isnot(None),
        )
    )
    rows = session.execute(stmt).scalars().all()
    by_psv: dict[uuid.UUID, list[ReliefResult]] = {}
    for r in rows:
        # selected_psv_id IS NOT NULL 已过滤；类型 narrowing 由 orm 行为保证
        psv_id = r.selected_psv_id
        if psv_id is None:
            continue
        by_psv.setdefault(psv_id, []).append(r)

    out: list[FlarePsvContribution] = []
    for psv_id, items in by_psv.items():
        dominant = max(items, key=lambda r: r.required_relief_area or 0.0)
        area = dominant.required_relief_area or 0.0
        # relief_scenario 是 ReliefScenario 枚举；用 .value 取字符串（与 dict key 对齐）
        scenario_str = (
            dominant.relief_scenario.value
            if hasattr(dominant.relief_scenario, "value")
            else str(dominant.relief_scenario)
        )
        out.append(
            FlarePsvContribution(
                psv_id=psv_id,
                dominant_scenario=scenario_str,
                required_relief_area_cm2=area,
                scenario_count=len(items),
            )
        )
    return out


def aggregate_flare_load(
    session: Session,
    project_id: uuid.UUID,
    standard_profile_code: str,
    sign_status_filter: tuple[str, ...] = ("CHECKED", "CHANGED"),
) -> FlareLoad:
    """项目级 FLARE_SYS 泄放汇总（多 PSV 叠加 + standard_profile_code 隔离）。

    流程：

      1. 取项目内所有有效 ReliefResult（按 ``standard_profile_code`` 过滤 +
         ``sign_status`` 过滤 + ``selected_psv_id IS NOT NULL``）
      2. 按 PSV 分组，每 PSV 取 max ``required_relief_area`` 对应 scenario
         作为主导（API 521 §5.15.4 保守原则）
      3. 跨 PSV 按主导 scenario 求和 ``required_relief_area``，输出
         ``per_scenario_total_cm2``

    Args:
        session: SQLAlchemy sync Session（P5-3-6 persist 同源约定）
        project_id: 项目 UUID
        standard_profile_code: 标准配置 code（API_521 / GB_T_150_1 / CUSTOM）
        sign_status_filter: 计入的 sign_status 集合（默认 CHECKED + CHANGED）

    Returns:
        FlareLoad dataclass — per_scenario_total / per_psv_dominant / total

    Raises:
        FlareAggregatorInputError: 输入不合法（空 project_id / 空 standard_profile_code）
    """
    if not project_id:
        raise FlareAggregatorInputError("project_id 不能为空")
    if not standard_profile_code:
        raise FlareAggregatorInputError("standard_profile_code 不能为空")

    per_psv = _per_psv_dominant(
        session, project_id, standard_profile_code, sign_status_filter
    )

    per_scenario_total: dict[str, float] = {}
    for contrib in per_psv:
        per_scenario_total[contrib.dominant_scenario] = (
            per_scenario_total.get(contrib.dominant_scenario, 0.0)
            + contrib.required_relief_area_cm2
        )

    return FlareLoad(
        project_id=project_id,
        standard_profile_code=standard_profile_code,
        per_scenario_total_cm2=per_scenario_total,
        per_psv_dominant=tuple(per_psv),
        total_psv_count=len(per_psv),
        total_relief_area_cm2=sum(per_scenario_total.values()),
        sign_status_filter=sign_status_filter,
    )


__all__ = [
    "Scenario",
    "FlareLoad",
    "FlarePsvContribution",
    "FlareAggregatorInputError",
    "aggregate_flare_load",
]