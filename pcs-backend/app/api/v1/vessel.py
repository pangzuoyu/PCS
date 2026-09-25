"""P5-1-4 VESSEL API：POST /calculate 端点契约。

端点：
- POST /api/v1/vessel/calculate
    body: {
        source_stream_id,
        sizing: { vessel_type, rho_L_kg_m3, rho_V_kg_m3, liquid_flow_m3_s,
                  vapor_flow_m3_s, residence_time_min, K_factor_ms },
        hydraulics: { D_m, L_m, h0_m, d_orifice_m, Cd_orifice,
                      Q_in_liquid_m3_s, d_overflow_m, h_overflow_m,
                      Cd_overflow, orientation, thermal_breathing_factor? },
        sizing_spec?: { vessel_shape, diameter_m, length_m, head_type,
                        operating_pressure_kpa, operating_temperature_c,
                        oil/water/gas_mass_rate_kg_d, oil/water/gas_density_kg_m3,
                        oil/water/gas_sg, gas_mw_kg_kmol, k_factor,
                        nozzle_inlet/outlet_momentum_limit_kg_m_s2,
                        instrument_response_time_s, n_vessels?, imperial_units? }
    }

P6-4 T2 扩展：可选 sizing_spec（C-08 两相分离器尺寸 V1.2 重写）触发
two_phase_separator_sizing_service，填充 vessel_results 6 列 sizing
（vmax_m_s / csa_min_m2 / csa_actual_m2 / nozzle_min_id_m / control_height_m /
residence_time_s）。sizing_spec=None 时保持 V1.0 兼容（不写 6 列）。

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 flash 一致）
- 业务异常 → core.errors.PcsError envelope（422/403/404 一致）
- 共用 vessel_persist 调度（service 层统一流程：守卫 → 计算 → 落库 → outlet → commit）
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.calc_entry import check_calc_inputs
from app.services.exceptions import PcsError
from app.services.vessel import vessel_persist
from app.services.vessel.two_phase_separator_sizing_service import (
    TwoPhaseSeparatorSizingInput,
)
from app.services.vessel.vessel_service import (
    VesselHydraulicsInput,
    VesselSizingInput,
)

router = APIRouter(prefix="/vessel", tags=["vessel"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class SizingInputSchema(BaseModel):
    """sizing 输入（对应 VesselSizingInput 物理量）。"""

    vessel_type: str = Field(
        ..., description="容器类型：VERTICAL 立式 / HORIZONTAL 卧式 / WITH_DEMISTER 带除雾器"
    )
    rho_L_kg_m3: float = Field(..., gt=0, description="液相密度 kg/m³")
    rho_V_kg_m3: float = Field(..., gt=0, description="气相密度 kg/m³")
    liquid_flow_m3_s: float = Field(..., gt=0, description="液相流量 m³/s")
    vapor_flow_m3_s: float = Field(..., gt=0, description="气相流量 m³/s")
    residence_time_min: float = Field(
        0.0, ge=0, description="停留时间 min（0 = 按 vessel_type 默认区间中值）"
    )
    K_factor_ms: float = Field(..., ge=0.01, le=1.0, description="K 因子 m/s（SI 物理范围）")


class HydraulicsInputSchema(BaseModel):
    """hydraulics 输入（对应 VesselHydraulicsInput 物理量）。"""

    D_m: float = Field(..., gt=0, description="容器直径 m")
    L_m: float = Field(..., gt=0, description="容器长度 m（立式罐即高度）")
    h0_m: float = Field(..., gt=0, description="初始液位 m（重力排空起点）")
    d_orifice_m: float = Field(..., gt=0, description="排空孔口直径 m")
    Cd_orifice: float = Field(..., gt=0, le=1, description="孔口流量系数")
    Q_in_liquid_m3_s: float = Field(0.0, ge=0, description="进液流量 m³/s")
    d_overflow_m: float = Field(..., gt=0, description="溢流口直径 m")
    h_overflow_m: float = Field(..., gt=0, description="溢流口距底部高度 m")
    Cd_overflow: float = Field(..., gt=0, le=1, description="溢流口流量系数")
    orientation: str = Field(
        "vertical",
        description="容器朝向：vertical/horizontal（horizontal 触发 UserWarning）",
    )
    thermal_breathing_factor: float = Field(
        1.0, gt=0, description="API 2000 表 4 Y 系数（默认 1.0）"
    )


class SizingSpecSchema(BaseModel):
    """两相分离器尺寸输入（对应 TwoPhaseSeparatorSizingInput）。

    可选字段（None = V1.0 兼容，不触发 sizing 计算）。
    P6-4 T2 C-08 V1.2 重写：5 段计算（Souders-Brown + CSA + 喷嘴 + 仪表 + 停留时间）。
    """

    vessel_shape: str = Field(
        ..., description="容器方位：VERTICAL 立式 / HORIZONTAL 卧式 / SPHERICAL 球罐",
    )
    diameter_m: float = Field(..., gt=0, description="容器内径 m")
    length_m: float = Field(
        0.0, ge=0, description="切线长 m（立式=高度；卧式=切线；球罐=0）",
    )
    head_type: str = Field(
        ..., description=(
            "封头类型：HEMISPHERICAL 半球 / 2:1_ELLIPTICAL 2:1椭圆 / "
            "TORISPHERICAL 碟形 / FLAT 平封头"
        ),
    )
    operating_pressure_kpa: float = Field(..., ge=0, description="操作压力 kPa(gauge)")
    operating_temperature_c: float = Field(..., description="操作温度 °C")
    oil_mass_rate_kg_d: float = Field(..., ge=0, description="油质量流量 kg/d")
    water_mass_rate_kg_d: float = Field(0.0, ge=0, description="水质量流量 kg/d")
    gas_mass_rate_kg_d: float = Field(..., ge=0, description="气质量流量 kg/d")
    oil_density_kg_m3: float = Field(..., gt=0, description="油密度 kg/m³")
    water_density_kg_m3: float = Field(..., gt=0, description="水密度 kg/m³")
    gas_density_kg_m3: float = Field(..., gt=0, description="气密度 kg/m³")
    oil_sg: float = Field(..., gt=0, description="油比重 SG（= oil_density/999.0）")
    water_sg: float = Field(..., gt=0, description="水比重 SG（= water_density/999.0）")
    gas_sg: float = Field(..., gt=0, description="气比重 SG（= gas_density/1.225）")
    gas_mw_kg_kmol: float = Field(..., gt=0, description="气分子量 kg/kmol")
    k_factor: float = Field(
        ..., ge=0.01, le=1.0, description="Souders-Brown K 因子 m/s",
    )
    nozzle_inlet_momentum_limit_kg_m_s2: float = Field(
        ..., gt=0, description="入口喷嘴动量限值 kg·m/s²",
    )
    nozzle_outlet_momentum_limit_kg_m_s2: float = Field(
        ..., gt=0, description="出口喷嘴动量限值 kg·m/s²",
    )
    instrument_response_time_s: float = Field(
        ..., gt=0, description="仪表响应时间 t_c s",
    )
    design_pressure_mpa: float = Field(1.0, gt=0, description="设计压力 MPa")
    n_vessels: int = Field(1, ge=1, description="并联容器数")
    imperial_units: bool = Field(False, description="是否输出英制转换字段")


class CalculateRequest(BaseModel):
    """POST /vessel/calculate 请求体。"""

    source_stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    sizing: SizingInputSchema = Field(..., description="vessel 尺寸计算输入")
    hydraulics: HydraulicsInputSchema = Field(..., description="vessel 流体力学校核输入")
    sizing_spec: SizingSpecSchema | None = Field(
        None, description=(
            "P6-4 T2 两相分离器尺寸（C-08 V1.2）；None = V1.0 兼容不计算"
        ),
    )


class CalculateResponse(BaseModel):
    """POST /vessel/calculate 响应：vessel_id + record_hash + lineage_ids + outlet。"""

    calc_id: uuid.UUID = Field(
        ..., description="VesselResult 主键 vessel_id（容器计算记录 UUID）"
    )
    calc_type: str = Field("VESSEL", description="计算类型（固定 VESSEL）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    stream_id: uuid.UUID = Field(..., description="源流 UUID")
    lineage_ids: list[uuid.UUID] = Field(
        default_factory=list, description="DataLineage 行 ID 列表"
    )
    result: dict[str, Any] = Field(
        default_factory=dict, description="合并 sizing + hydraulics + sizing_spec 结果"
    )
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID")
    outlet_stream_name: str = Field(..., description="出口流名称")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 flash.py 一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


async def _lineage_ids(db: AsyncSession, calc_id: uuid.UUID) -> list[uuid.UUID]:
    """查 vessel_id 的血缘 ID 列表（DataLineage.source_ref_id 已记录）。"""
    from sqlalchemy import select

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage.lineage_id).where(
                DataLineage.record_type == "VesselResult",
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
async def calculate_vessel(
    req: CalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalculateResponse:
    """POST /api/v1/vessel/calculate：vessel 尺寸 + 流体力学 + 两相 sizing 一次计算。

    P6-4 T2：可选 sizing_spec 触发 two_phase_separator_sizing_service（C-08 V1.2
    重写），填充 vessel_results 6 列 sizing；sizing_spec=None 时保持 V1.0 兼容。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 0. 三步守卫（物流存在 → CHECKED → 不可靠流）
    await check_calc_inputs(db, [req.source_stream_id])

    try:
        # 1. Pydantic schema → dataclass 转换
        sizing_inp = VesselSizingInput(**req.sizing.model_dump())
        hydraulics_inp = VesselHydraulicsInput(**req.hydraulics.model_dump())
        # P6-4 T2 可选 sizing_spec → TwoPhaseSeparatorSizingInput
        sizing_spec_inp: TwoPhaseSeparatorSizingInput | None = None
        if req.sizing_spec is not None:
            sizing_spec_inp = TwoPhaseSeparatorSizingInput(
                **req.sizing_spec.model_dump()
            )

        # 2. service 层落库
        data = await vessel_persist.persist_vessel_calculate(
            db,
            source_stream_id=req.source_stream_id,
            sizing_input=sizing_inp,
            hydraulics_input=hydraulics_inp,
            sizing_spec_input=sizing_spec_inp,
            actor=user.user_id,
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
