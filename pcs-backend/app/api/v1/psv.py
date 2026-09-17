"""P5-3-6 PSV API：POST /calculate 端点契约。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §395-417 + SUP-P5-PSV-001 + ADR-0028 V1.1：

端点：
- POST /api/v1/psv/calculate
    body: {
        source_stream_id,
        relief_scenario: FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION,
        scenario_params: 对应 Input dataclass 字段（FireCaseInput / ClosedValveInput /
                         ReactionRunawayInput / ThermalExpansionInput），
        sizing_params: ReliefAreaInput 字段（phase + P_back + P_set + ...），
        standard_code?: API / GB / CUSTOM（默认项目默认），
        standard_version?: 7th / 2011 / 2024（默认推断），
        blowdown_fraction?: 0.05 默认，
        inlet_size?: "4 inch" 默认，
        outlet_size?: "6 inch" 默认
    }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 vessel / sep_equip 一致）
- 业务异常 → core.errors.PcsError envelope（422/403/404）
- 共用 psv_persist 调度（service 层统一流程：守卫 → 项目 profile → 计算 → 落库 → outlet）
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.exceptions import PcsError
from app.services.psv import persist_psv_calculate

router = APIRouter(prefix="/psv", tags=["psv"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


ReliefScenarioLit = Literal[
    "FIRE", "CLOSED_VALVE", "REACTION_RUNAWAY", "THERMAL_EXPANSION",
]
StandardCodeLit = Literal["API", "GB", "CUSTOM"]

# P5-OPEN-10 SUP-P5-PSV-002 V1.14 §4.1 Pydantic Literal 枚举
PsvValveTypeLit = Literal["SPRING_LOADED", "BALANCED_BELLOWS", "PILOT_OPERATED", "RUPTURE_DISC"]
PsvBodyMaterialLit = Literal["CARBON_STEEL", "SS304", "SS316", "SS316L", "ALLOY"]
PsvBellowsMaterialLit = Literal[
    "HASTELLOY_C276", "SS316L", "INCONEL_625", "INCONEL_718", "ALLOY_400", "ALLOY_C22",
]
PsvFlangeClassLit = Literal["150#", "300#", "600#", "900#", "1500#", "2500#"]
PsvBackPressureTypeLit = Literal["BUILT_UP", "SUPERIMPOSED"]
PsvMediumLit = Literal["GAS", "VAPOR", "LIQUID", "TWO_PHASE"]
PsvOrificeSizeLit = Literal[
    "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "T",
]
PsvRuptureDiscPositionLit = Literal["UPSTREAM", "DOWNSTREAM", "NONE"]
PsvPilotTempClassLit = Literal["GENERAL", "HIGH_TEMP", "CRYOGENIC"]


class CalculateRequest(BaseModel):
    """POST /psv/calculate 请求体。

    P5-OPEN-10 V1.14：新增 18 字段与前端 §4.1 联动；老请求可用（extra='ignore'）。
    """

    # forward-compat：未识别字段静默丢弃；后端 Pydantic v2 不阻断老客户端
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    source_stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    relief_scenario: ReliefScenarioLit = Field(
        ...,
        description="FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION",
    )
    scenario_params: dict[str, Any] = Field(
        ...,
        description=(
            "工况参数：按 relief_scenario 路由 FireCaseInput / ClosedValveInput / "
            "ReactionRunawayInput / ThermalExpansionInput 对应字段"
        ),
    )
    sizing_params: dict[str, Any] = Field(
        ...,
        description="ReliefAreaInput 字段（phase + P_back + P_set + ...）",
    )
    standard_code: StandardCodeLit | None = Field(
        default=None,
        description="API / GB / CUSTOM；缺省走项目默认 PSV profile",
    )
    standard_version: str | None = Field(
        default=None,
        description="7th / 2011 / 2024 / CUSTOM；缺省由项目 profile 推断",
    )
    blowdown_fraction: float | None = Field(
        default=None,
        description=(
            "blowdown 占比（API 520 惯例 5%）；None → 按 medium 派生（GAS=5% / "
            "VAPOR=5% / LIQUID=10% / TWO_PHASE=10%；§3.5）"
        ),
    )
    inlet_size: str = Field(default="4 inch", description="进口尺寸")
    outlet_size: str = Field(default="6 inch", description="出口尺寸")

    # ===== P5-OPEN-10 SUP-P5-PSV-002 V1.14 §4.1 选型 18 字段（全部 Optional + 默认值）=====
    valve_type: PsvValveTypeLit = Field(
        default="SPRING_LOADED",
        description="SPRING_LOADED / BALANCED_BELLOWS / PILOT_OPERATED / RUPTURE_DISC",
    )
    body_material: PsvBodyMaterialLit = Field(
        default="SS316",
        description="阀体材料 CARBON_STEEL / SS304 / SS316 / SS316L / ALLOY",
    )
    bellows_material: PsvBellowsMaterialLit | None = Field(
        default=None,
        description="波纹管材料 6 种（仅 BALANCED_BELLOWS 必填；§3.8）",
    )
    flange_class: PsvFlangeClassLit = Field(
        default="300#",
        description="法兰等级 150#/300#/600#/900#/1500#/2500#",
    )
    back_pressure_type: PsvBackPressureTypeLit = Field(
        default="BUILT_UP",
        description="BUILT_UP（累积）/ SUPERIMPOSED（恒定叠加）",
    )
    back_pressure_pct: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="背压百分比 0-100（弹簧式 BUILT_UP 上限 10%；§3.5）",
    )
    superimposed_pressure_pa: float = Field(
        default=0.0,
        ge=0,
        description="恒定叠加背压（Pa；仅 SUPERIMPOSED 时启用 CDTP 修正；§4.4）",
    )
    set_pressure_pa: float = Field(
        default=200_000.0,
        gt=0,
        description="设定压力（Pa gauge；前端透传 stream.max_allowable_pressure_pa）",
    )
    overpressure_pct: float = Field(
        default=0.10,
        description="超压百分比 10/16/21（API 520 §5.3.1）",
    )
    orifice_override: PsvOrificeSizeLit | None = Field(
        default=None,
        description="手动指定孔口 D-T（与 API 526 反向映射候选一致；§4.5）",
    )
    valve_brand: str | None = Field(
        default=None,
        description="阀体品牌（自由字符串；V1.14 P2-1 修订；§4.3）",
    )
    rupture_disc_position: PsvRuptureDiscPositionLit = Field(
        default="NONE",
        description="爆破膜位置 UPSTREAM（Kc=0.90）/ DOWNSTREAM（Kc=1.00）/ NONE",
    )
    pilot_temperature_c: float | None = Field(
        default=None,
        description="先导温度 °C（PILOT_OPERATED；P5 占位）",
    )
    pilot_temp_class: PsvPilotTempClassLit = Field(
        default="GENERAL",
        description="GENERAL / HIGH_TEMP / CRYOGENIC（PILOT_OPERATED；P5 占位）",
    )
    fire_protection: bool = Field(
        default=False,
        description="防火保护（影响 FIRE 工况计算；§3.2）",
    )
    medium: PsvMediumLit = Field(
        default="GAS",
        description="介质 GAS / VAPOR / LIQUID / TWO_PHASE",
    )
    service_note: str | None = Field(
        default=None,
        description="服务工况备注（人工输入；含介质描述，用于波纹管材料兼容校验；§3.8）",
    )
    fluid_temperature_c: float | None = Field(
        default=None,
        description="流体温度 °C（Q/R/T 高温低分子量校验用；§3.9）",
    )
    molecular_weight: float | None = Field(
        default=None,
        description="分子量 g/mol（Q/R/T 高温低分子量校验用；§3.9）",
    )
    calculated_area_m2: float | None = Field(
        default=None,
        description="计算泄放面积 m²（G9 orifice_override < 计算面积 校验用；§4.2 G9）",
    )


class CalculateResponse(BaseModel):
    """POST /psv/calculate 响应。"""

    calc_id: uuid.UUID = Field(..., description="PsvResult.psv_id")
    calc_type: str = Field("PSV", description="计算类型（固定 PSV）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    stream_id: uuid.UUID = Field(..., description="源流 UUID")
    lineage_ids: list[uuid.UUID] = Field(
        default_factory=list, description="DataLineage 行 ID 列表"
    )
    result: dict[str, Any] = Field(
        default_factory=dict,
        description="完整 PSV 计算结果（scenario + aggregate + area + orifice + formula_ref）",
    )
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID")
    outlet_stream_name: str = Field(..., description="出口流名称")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 vessel.py 一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


async def _lineage_ids(
    db: AsyncSession, calc_id: uuid.UUID
) -> list[uuid.UUID]:
    """查 psv_id 的血缘 ID 列表（DataLineage.source_ref_id 已记录）。"""
    from sqlalchemy import select

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage.lineage_id).where(
                DataLineage.record_type == "PsvResult",
                DataLineage.record_id == calc_id,
            )
        )
    ).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/calculate",
    status_code=201,
    response_model=CalculateResponse,
)
async def calculate_psv(
    req: CalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalculateResponse:
    """POST /api/v1/psv/calculate：PSV 单工况计算落库。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        data = await persist_psv_calculate(
            db,
            source_stream_id=req.source_stream_id,
            relief_scenario=req.relief_scenario,
            scenario_params=req.scenario_params,
            sizing_params=req.sizing_params,
            standard_code=req.standard_code,
            standard_version=req.standard_version,
            blowdown_fraction=req.blowdown_fraction,
            inlet_size=req.inlet_size,
            outlet_size=req.outlet_size,
            actor=user.user_id,
            # ===== P5-OPEN-10 V1.14 §4.1 选型 18 字段透传 =====
            valve_type=req.valve_type,
            body_material=req.body_material,
            bellows_material=req.bellows_material,
            flange_class=req.flange_class,
            back_pressure_type=req.back_pressure_type,
            back_pressure_pct=req.back_pressure_pct,
            superimposed_pressure_pa=req.superimposed_pressure_pa,
            set_pressure_pa=req.set_pressure_pa,
            overpressure_pct=req.overpressure_pct,
            orifice_override=req.orifice_override,
            valve_brand=req.valve_brand,
            rupture_disc_position=req.rupture_disc_position,
            pilot_temperature_c=req.pilot_temperature_c,
            pilot_temp_class=req.pilot_temp_class,
            fire_protection=req.fire_protection,
            medium=req.medium,
            service_note=req.service_note,
            fluid_temperature_c=req.fluid_temperature_c,
            molecular_weight=req.molecular_weight,
            calculated_area_m2=req.calculated_area_m2,
        )
    except PcsError as e:
        raise _to_http(e) from e

    lineage_ids = await _lineage_ids(db, data["calc_id"])
    return CalculateResponse(
        calc_id=data["calc_id"],
        calc_type=data["calc_type"],
        record_hash=data["record_hash"],
        stream_id=data["stream_id"],
        lineage_ids=lineage_ids,
        result=data.get("result", {}),
        outlet_stream_id=data["outlet_stream_id"],
        outlet_stream_name=data["outlet_stream_name"],
    )


__all__ = ["router"]