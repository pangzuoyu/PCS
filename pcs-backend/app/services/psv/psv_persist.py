"""P5-3-6 PSV 计算落库 + outlet 流（service 层）。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §395-417 + SUP-P5-PSV-001 + ADR-0028 V1.1：

设计要点：
1. check_calc_inputs 三步守卫（DRAFT → 403 / 不可靠 → 422 / 不存在 → 404）
2. 读取源流（提供 project_id / workspace_id）+ 项目默认 standard profile
3. 按 relief_scenario dispatcher 调对应 service（fire_case / other_cases）
4. 构造 ReliefCase + 调 calc_relief_aggregate（取 max W_mass）
5. 调 calc_relief_area 算 area_required_m2
6. 调 select_orifice_api526 选 orifice_designation + actual_area
7. 构造 PsvResult ORM（12 标量 + 5 JSONB）+ 落库
8. finalize_calc_record（record_hash + lineage）
9. create_outlet_stream(source_type='PSV_CALCULATED')
10. commit + 返回 psv_id + record_hash + outlet_stream_id

PsvResult 不带 input_json/output_json 列（详 calc.py L162-227）；
详细 input/output 走 standard_refs_json + formula_ref_json，OUT 返回完整
dict 由 service 层组装（不入 DB）。

P5-3-6 V1 简化：单工况（4 选 1）。多工况叠加已由 P5-3-3 aggregate 服务就绪，
扩展点：relief_scenario 改 list + ReliefCase 多次。

不做：
- 不并发锁（与 vessel_persist 一致）
- 不写 psv_results 之外的派生表
- 不显式处理 CUSTOM profile（待 P5-3-7 扩展；当前走项目默认）
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PsvResult
from app.models.project import Stream
from app.models.psv_standards import ProjectCalculationStandardProfile
from app.services.calc_entry import check_calc_inputs
from app.services.calc_lineage import finalize_calc_record
from app.services.exceptions import PcsError
from app.services.outlet_stream import create_outlet_stream
from app.services.psv.fire_case_service import (
    FireCaseInput,
    calc_fire_case,
)
from app.services.psv.orifice_service import (
    OrificeInput,
    select_orifice_api526,
)
from app.services.psv.other_cases_service import (
    ClosedValveInput,
    ReactionRunawayInput,
    ThermalExpansionInput,
    calc_closed_valve_case,
    calc_reaction_runaway_case,
    calc_thermal_expansion_case,
)
from app.services.psv.relief_aggregator_service import (
    ReliefAggregateInput,
    ReliefCase,
    Scenario,
    calc_relief_aggregate,
)
from app.services.psv.relief_area_service import (
    ReliefAreaInput,
    calc_relief_area,
)

# P5-3-6 formula_version：固定锚点（CIA 引擎版本对齐时一并 bump）
_FORMULA_VERSION = "PSv1.0-p5-3-6"

# 默认 PSV 几何（V1 锁定；P5-3-7 端点可覆盖）
_DEFAULT_INLET_SIZE: Final[str] = "4 inch"
_DEFAULT_OUTLET_SIZE: Final[str] = "6 inch"
_DEFAULT_BLOWDOWN_FRACTION: Final[float] = 0.05

# 默认 standard profile（项目级缺省走 API/7th）
_DEFAULT_STANDARD_CODE: Final[str] = "API"
_DEFAULT_STANDARD_VERSION: Final[str] = "7th"


# ---------- Helpers ----------


def _generate_tag_number(project_id: uuid.UUID) -> str:
    """生成项目内唯一 PsvResult tag_number。

    格式：``PSV-{short_uuid}``（短码 8 位 hex；项目内由 DB unique 约束兜底）。
    """
    return f"PSV-{uuid.uuid4().hex[:8].upper()}"


def _dataclass_to_dict(dc: Any) -> dict:
    """frozen dataclass → dict（用于 result dict 序列化）。"""
    return dataclasses.asdict(dc)


def _formula_ref_to_dict(ref: object) -> dict:
    """formula_ref 系列 → dict。"""
    if hasattr(ref, "__dataclass_fields__"):
        return dataclasses.asdict(ref)  # type: ignore[arg-type]
    if isinstance(ref, dict):
        return dict(ref)
    return {"raw": str(ref)}


def _default_standard_refs() -> dict:
    """无项目默认 profile 时走全局默认 API/7th 标准引用集合。"""
    return {
        "fire_case": {
            "standard": "API_521",
            "version": "7th",
            "clause": "§5.15.2.2.1 / Table 5",
        },
        "relief_area": {
            "standard": "API_520",
            "version": "7th",
            "clause": "§5.6.3",
        },
        "orifice": {
            "standard": "API_526",
            "version": "7th",
            "clause": "Table 1 / Table 2",
        },
    }


# ---------- Project standard profile 读取 ----------


async def _resolve_standard_profile(
    db: AsyncSession,
    project_id: uuid.UUID,
    requested_code: str | None,
    requested_version: str | None,
) -> tuple[str, str, dict]:
    """解析项目默认标准配置（project_calculation_standard_profiles）。

    查项目 PSV discipline 当前默认 profile（is_default=TRUE + migrated_default=FALSE
    + effective_to IS NULL）；如未配置走全局默认 API/7th。

    Returns:
        (profile_code, version, standard_refs_dict)
    """
    stmt = (
        select(ProjectCalculationStandardProfile)
        .where(
            ProjectCalculationStandardProfile.project_id == project_id,
            ProjectCalculationStandardProfile.discipline == "PSV",
            ProjectCalculationStandardProfile.is_default.is_(True),
            ProjectCalculationStandardProfile.migrated_default.is_(False),
            ProjectCalculationStandardProfile.effective_to.is_(None),
        )
        .limit(1)
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()

    if profile is not None:
        code = requested_code or profile.profile_code
        version = requested_version or _infer_default_version(profile)
        refs = dict(profile.standard_refs_json or {})
        return code, version, refs

    code = requested_code or _DEFAULT_STANDARD_CODE
    version = requested_version or _DEFAULT_STANDARD_VERSION
    refs = _default_standard_refs()
    return code, version, refs


def _infer_default_version(profile: ProjectCalculationStandardProfile) -> str:
    """从 profile.standard_refs_json 推断默认版本。"""
    refs = profile.standard_refs_json or {}
    fire_case = refs.get("fire_case", {})
    version = fire_case.get("version")
    if isinstance(version, str):
        return version
    return _DEFAULT_STANDARD_VERSION


# ---------- Scenario dispatcher ----------


def _dispatch_scenario_calc(
    scenario: Scenario,
    scenario_params: dict,
    standard: str,
    version: str,
) -> ReliefCase:
    """按 scenario 分发调对应 calc 函数，构造 ReliefCase。

    Returns:
        ReliefCase（scenario + relief_mass_flow_kgs + relief_volume_flow_m3s + formula_ref）
    """
    if scenario == "FIRE":
        inp = FireCaseInput(**scenario_params)
        result = calc_fire_case(inp, standard=standard, version=version)  # type: ignore[arg-type]
        return ReliefCase(
            scenario="FIRE",
            relief_mass_flow_kgs=result.relief_mass_flow_kgs,
            relief_volume_flow_m3s=result.relief_volume_flow_m3s,
            formula_ref=_formula_ref_to_dict(result.formula_ref),
        )
    if scenario == "CLOSED_VALVE":
        inp = ClosedValveInput(**scenario_params)
        result = calc_closed_valve_case(inp)
        return ReliefCase(
            scenario="CLOSED_VALVE",
            relief_mass_flow_kgs=result.relief_mass_flow_kgs,
            relief_volume_flow_m3s=result.relief_volume_flow_m3s,
            formula_ref=_formula_ref_to_dict(result.formula_ref),
        )
    if scenario == "REACTION_RUNAWAY":
        inp = ReactionRunawayInput(**scenario_params)
        result = calc_reaction_runaway_case(inp)
        return ReliefCase(
            scenario="REACTION_RUNAWAY",
            relief_mass_flow_kgs=result.relief_mass_flow_kgs,
            relief_volume_flow_m3s=0.0,  # 反应失控无体积流量输出
            formula_ref=_formula_ref_to_dict(result.formula_ref),
        )
    if scenario == "THERMAL_EXPANSION":
        inp = ThermalExpansionInput(**scenario_params)
        result = calc_thermal_expansion_case(inp)
        return ReliefCase(
            scenario="THERMAL_EXPANSION",
            relief_mass_flow_kgs=result.relief_mass_flow_kgs,
            relief_volume_flow_m3s=result.relief_volume_flow_m3s,
            formula_ref=_formula_ref_to_dict(result.formula_ref),
        )
    raise PcsError(
        f"relief_scenario={scenario} 不在 4 种支持范围",
        code="PSV_INPUT_ERROR",
        status=422,
    )


# ---------- Core entry ----------


async def persist_psv_calculate(
    db: AsyncSession,
    *,
    source_stream_id: uuid.UUID,
    relief_scenario: Scenario,
    scenario_params: dict[str, Any],
    sizing_params: dict[str, Any],
    standard_code: str | None = None,
    standard_version: str | None = None,
    blowdown_fraction: float = _DEFAULT_BLOWDOWN_FRACTION,
    inlet_size: str = _DEFAULT_INLET_SIZE,
    outlet_size: str = _DEFAULT_OUTLET_SIZE,
    actor: uuid.UUID | None = None,
) -> dict[str, Any]:
    """PSV 计算落库：scenario → aggregate → area → orifice → PsvResult + outlet。

    Args:
        db: async session
        source_stream_id: 源流 UUID（必填，触发 CHECKED 守卫）
        relief_scenario: FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION
        scenario_params: 4 种 Input dataclass 对应字段（FireCaseInput / ClosedValveInput /
                         ReactionRunawayInput / ThermalExpansionInput）
        sizing_params: ReliefAreaInput 对应字段（phase + P_back + P_set + ...）
        standard_code: API / GB / CUSTOM（默认项目默认；待 P5-3-7 完整开放）
        standard_version: 7th / 2011 / 2024 / CUSTOM（默认推断）

    Returns:
        {
            "calc_id", "calc_type", "record_hash",
            "stream_id", "result"（dict）, "outlet_stream_id", "outlet_stream_name",
        }

    Raises:
        PcsError: 三步守卫失败 / 源流不存在 / 工况不支持 / standard 不支持
    """
    # 1. 三步守卫
    await check_calc_inputs(db, [source_stream_id])

    # 2. 读源流
    stream = await db.get(Stream, source_stream_id)
    if stream is None:
        raise PcsError(
            f"Stream {source_stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )

    # 3. 解析 standard profile
    profile_code, version, standard_refs = await _resolve_standard_profile(
        db, stream.project_id, standard_code, standard_version,
    )

    # 4. 调对应工况计算
    relief_case = _dispatch_scenario_calc(
        relief_scenario, scenario_params, profile_code, version,
    )

    # 5. 构造 ReliefAggregateInput（单工况 V1 简化）
    aggregate = calc_relief_aggregate(ReliefAggregateInput(cases=(relief_case,)))

    # 6. 调泄放面积计算
    area_input = ReliefAreaInput(**sizing_params)
    area_result = calc_relief_area(
        area_input, standard=profile_code,  # type: ignore[arg-type]
    )

    # 7. 调孔口选型
    orifice_result = select_orifice_api526(
        OrificeInput(area_required_m2=area_result.area_required_m2),
    )

    # 8. 构造 PsvResult ORM
    set_pressure_pa = float(sizing_params.get("P_set_pa", 0.0))
    relief_scenario_list: list[str] = [relief_scenario]

    formula_ref_json: dict = {
        "fire_case_or_other": relief_case.formula_ref,
        "relief_area": _formula_ref_to_dict(area_result.formula_ref),
        "orifice": _formula_ref_to_dict(orifice_result.formula_ref),
        "dominant_scenario": aggregate.dominant_scenario,
    }

    record = PsvResult(
        tag_number=_generate_tag_number(stream.project_id),
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
        set_pressure=set_pressure_pa,
        relief_capacity=aggregate.max_relief_mass_flow_kgs,
        orifice_area=orifice_result.actual_area_m2,
        blowdown=blowdown_fraction,
        orifice_designation=orifice_result.selected_size,
        inlet_size=inlet_size,
        outlet_size=outlet_size,
        relief_scenario=relief_scenario_list,
        standard_profile_code=profile_code,
        standard_refs_json=standard_refs,
        formula_ref_json=formula_ref_json,
        pending_review=False,
        migrated_default=False,
    )
    db.add(record)
    await db.flush()  # psv_id 落库（finalize 内 LineageTracker 需要 PK）

    # 9. finalize_calc_record（record_hash + lineage）
    await finalize_calc_record(
        db,
        record,
        source_stream_ids=[source_stream_id],
        formula_version=_FORMULA_VERSION,
    )

    # 10. outlet 流（source_type=PSV_CALCULATED）
    outlet = await create_outlet_stream(
        db,
        source_stream_id=source_stream_id,
        calc_type="PSV",
        source_type="PSV_CALCULATED",
        properties={
            "_calc_type": "PSV",
            "relief_scenario": relief_scenario,
            "dominant_scenario": aggregate.dominant_scenario,
            "set_pressure_pa": set_pressure_pa,
            "relief_capacity_kgs": aggregate.max_relief_mass_flow_kgs,
            "orifice_designation": orifice_result.selected_size,
            "orifice_area_m2": orifice_result.actual_area_m2,
            "blowdown_fraction": blowdown_fraction,
            "standard_profile_code": profile_code,
            "standard_version": version,
        },
        project_id=stream.project_id,
        workspace_id=stream.workspace_id,
    )
    await db.flush()

    # 11. commit
    await db.commit()

    # 12. 组装 OUT 详细结果（不入 DB）
    out_result: dict[str, Any] = {
        "relief_scenario": relief_scenario,
        "relief_case": {
            "scenario": relief_case.scenario,
            "relief_mass_flow_kgs": relief_case.relief_mass_flow_kgs,
            "relief_volume_flow_m3s": relief_case.relief_volume_flow_m3s,
            "formula_ref": relief_case.formula_ref,
        },
        "aggregate": {
            "max_relief_mass_flow_kgs": aggregate.max_relief_mass_flow_kgs,
            "max_relief_volume_flow_m3s": aggregate.max_relief_volume_flow_m3s,
            "dominant_scenario": aggregate.dominant_scenario,
            "case_count": aggregate.case_count,
        },
        "relief_area": _dataclass_to_dict(area_result),
        "orifice": _dataclass_to_dict(orifice_result),
        "set_pressure_pa": set_pressure_pa,
        "blowdown_fraction": blowdown_fraction,
        "inlet_size": inlet_size,
        "outlet_size": outlet_size,
        "standard_profile_code": profile_code,
        "standard_version": version,
        "formula_ref_json": formula_ref_json,
    }

    return {
        "calc_id": record.psv_id,
        "calc_type": "PSV",
        "record_hash": record.record_hash,
        "stream_id": source_stream_id,
        "result": out_result,
        "outlet_stream_id": outlet.stream_id,
        "outlet_stream_name": outlet.stream_name,
    }


__all__ = ["persist_psv_calculate", "Scenario"]