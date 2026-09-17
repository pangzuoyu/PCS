"""P5-2-4 SEP_EQUIP API：POST /calculate 端点契约。

端点：
- POST /api/v1/sep-equip/calculate
    body: {
        source_stream_id,
        device_type: 'CYCLONE' | 'MIST_ELIMINATOR' | 'GRAVITY' | 'VANE' | 'FIBER',
        params: 设备类型对应字段（CycloneInput / MistEliminatorInput / GravitySeparatorInput）
    }

设备类型 → 字段映射（service 层 dispatcher 构造对应 dataclass）：
- CYCLONE：D_cylinder_m, D_exhaust_m, a_inlet_m, b_inlet_m, V_in_ms,
            rho_kg_m3, mu_pa_s, rho_particle_kg_m3, N_effective_turns,
            method（LAPPLE/SWIFT/BARTH，默认 LAPPLE）
- MIST_ELIMINATOR：pad_type（STANDARD/HIGH_EFFICIENCY）, Q_gas_m3_s,
                    D_cylinder_m, rho_gas_kg_m3, mu_gas_pa_s, liquid_load_kg_m3
- GRAVITY/VANE/FIBER：d_particle_m, rho_particle_kg_m3, rho_fluid_kg_m3,
                       mu_fluid_pa_s, height_setting_m, horizontal_velocity_ms

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 vessel 一致）
- 业务异常 → core.errors.PcsError envelope（422/403/404）
- 共用 sep_equip_persist 调度
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
from app.services.sep_equip import sep_equip_persist

router = APIRouter(prefix="/sep-equip", tags=["sep-equip"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class CalculateRequest(BaseModel):
    """POST /sep-equip/calculate 请求体。"""

    source_stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    device_type: str = Field(
        ...,
        description="CYCLONE/MIST_ELIMINATOR/GRAVITY/VANE/FIBER",
    )
    params: dict[str, Any] = Field(
        ...,
        description="设备类型对应参数（字段名匹配对应 Input dataclass）",
    )


class CalculateResponse(BaseModel):
    """POST /sep-equip/calculate 响应。"""

    calc_id: uuid.UUID = Field(..., description="SepEquipResult.sep_equip_id")
    calc_type: str = Field(..., description="设备类型（= device_type）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    stream_id: uuid.UUID = Field(..., description="源流 UUID")
    lineage_ids: list[uuid.UUID] = Field(
        default_factory=list, description="DataLineage 行 ID 列表"
    )
    result: dict[str, Any] = Field(
        default_factory=dict, description="设备类型对应 result dict"
    )
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID")
    outlet_stream_name: str = Field(..., description="出口流名称")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(
        code=code, message=message, status=status, detail=details
    )


async def _lineage_ids(
    db: AsyncSession, calc_id: uuid.UUID
) -> list[uuid.UUID]:
    """查 sep_equip_id 的血缘 ID 列表。"""
    from sqlalchemy import select

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage.lineage_id).where(
                DataLineage.record_type == "SepEquipResult",
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
async def calculate_sep_equip(
    req: CalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalculateResponse:
    """POST /api/v1/sep-equip/calculate：5 类型 sep_equip 一次计算。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 0. 三步守卫（物流存在 → CHECKED → 不可靠流）
    await check_calc_inputs(db, [req.source_stream_id])

    try:
        data = await sep_equip_persist.persist_sep_equip_calculate(
            db,
            source_stream_id=req.source_stream_id,
            device_type=req.device_type,  # type: ignore[arg-type]
            params=req.params,
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