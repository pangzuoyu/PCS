"""P4-1-3 出口物流创建 helper（ADR-0022 集成点）。

复用面：
- P4-1-3 FLASH（FLASH_CALCULATED）— 本批次首建
- P4-2-5 PIPE 计算链（PIPE_CALCULATED）
- P4-3-3 PIPE_NET 管网（_NET_CALCULATED 后缀；P4-3-3 扩 Literal）
- P4-4-4 PUMP 计算链（PUMP_CALCULATED）
- **P5-1-4 VESSEL**（VESSEL_CALCULATED）— ADR-0032 V1.1 决策 6
- **P5-2-4 SEP_EQUIP**（SEP_EQUIP_CALCULATED）
- **P5-3-6 PSV**（PSV_CALCULATED）— ADR-0028 V1.1 + SUP-P5-PSV-001

设计要点：
- 独立可调用：不依赖 flash_persist；只接 db + 元数据
- sign_status=DRAFT（下游未 CHECKED 不可用，calc 入口守卫兜底）
- properties → stream.stream_properties_json（JSONB）
- source_type 走 Stream.source_type 字符串列
  （FLASH_CALCULATED/PIPE_CALCULATED/PUMP_CALCULATED/PIPE_NET_CALCULATED/
  VESSEL_CALCULATED）
- upstream_stream_id / upstream_equipment_type 用于溯源
- project_id 校验：必须与源流同 project，跨 project 抛 OutletStreamProjectMismatchError

不做：
- 不写 record_hash（Stream 自己的 record_hash 由 SIM-18 / P4-1-4 SIM 反向写时覆盖）
- 不调冲突检测（SIM-7 在 stream 创建入口已有；本 helper 假定上游已有）
"""
from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StreamSignStatus
from app.models.project import Stream
from app.services.exceptions import PcsError

# 出口物流 source_type 字面值（Stream.source_type 字符串列无 enum）
# P4-3-3 扩展：新增 "PIPE_NET_CALCULATED"（向前兼容，旧调用仍有效）
# P5-1-4 扩展：新增 "VESSEL_CALCULATED"（ADR-0032 V1.1 决策 6）
OutletSourceType = Literal[
    "FLASH_CALCULATED",
    "PIPE_CALCULATED",
    "PUMP_CALCULATED",
    "PIPE_NET_CALCULATED",
    "VESSEL_CALCULATED",
    "SEP_EQUIP_CALCULATED",
    "PSV_CALCULATED",
]


class OutletStreamProjectMismatchError(PcsError):
    """出口物流 project_id 与源流不一致（403/422）。"""

    code = "OUTLET_STREAM_PROJECT_MISMATCH"
    status = 422


# upstream_equipment_type 映射表
# （P4-3-3 扩 "PIPE_NET_CALCULATED" → "PIPE_NET"；其余按 source_type split_[0]
# 即可；集中维护以防 PIPE_NET_CALCULATED 被 split 出 "PIPE" 错值）
# P5-1-4 扩展：新增 "VESSEL_CALCULATED" → "VESSEL"
# P5-2-4 扩展：新增 "SEP_EQUIP_CALCULATED" → "SEP_EQUIP"
_EQUIP_TYPE_MAP: dict[str, str] = {
    "FLASH_CALCULATED": "FLASH",
    "PIPE_CALCULATED": "PIPE",
    "PUMP_CALCULATED": "PUMP",
    "PIPE_NET_CALCULATED": "PIPE_NET",
    "VESSEL_CALCULATED": "VESSEL",
    "SEP_EQUIP_CALCULATED": "SEP_EQUIP",
    "PSV_CALCULATED": "PSV",
}


def _upstream_equipment_type(source_type: str) -> str:
    """source_type → upstream_equipment_type 映射。

    已知类型查表；未知类型回退 source_type.split("_")[0]（向后兼容）。
    """
    if source_type in _EQUIP_TYPE_MAP:
        return _EQUIP_TYPE_MAP[source_type]
    return source_type.split("_")[0]


async def create_outlet_stream(
    db: AsyncSession,
    *,
    source_stream_id: uuid.UUID,
    calc_type: str,
    source_type: OutletSourceType,
    properties: dict,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Stream:
    """创建出口物流：sign_status=DRAFT；properties 入 stream_properties_json。

    Args:
        db: async session
        source_stream_id: 源流 UUID（写入 upstream_stream_id）
        calc_type: 计算类型（PT_FLASH/PH_FLASH/...；仅用于 stream_name 后缀）
        source_type: FLASH_CALCULATED/PIPE_CALCULATED/PUMP_CALCULATED
        properties: 出口物流属性（写入 stream_properties_json）
        project_id: 所属项目 UUID（必须与 source_stream_id 同 project）
        workspace_id: 所属工作区 UUID

    Returns:
        新建的 Stream ORM 实例（已 flush，sign_status=DRAFT）

    Raises:
        OutletStreamProjectMismatchError: project_id 与源流 project_id 不一致
        IntegrityError: stream_name 重复（unique 约束）
    """
    # 1. 源流校验 + project_id 一致性
    source = await db.get(Stream, source_stream_id)
    if source is None:
        raise PcsError(
            f"源流 {source_stream_id} 不存在，无法创建出口物流",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    if source.project_id != project_id:
        raise OutletStreamProjectMismatchError(
            f"出口物流 project_id={project_id} 与源流 project_id={source.project_id} 不一致",
            code=OutletStreamProjectMismatchError.code,
            status=OutletStreamProjectMismatchError.status,
        )

    # 2. 构造 outlet stream（stream_name 唯一：源流名 + 计算后缀 + uuid 短码）
    short = uuid.uuid4().hex[:6].upper()
    outlet = Stream(
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"{source.stream_name}-{calc_type}-{short}",
        case_type=source.case_type,
        data_mode=source.data_mode,
        description=f"出口物流（{source_type} / {calc_type}）",
        source_type=source_type,
        sign_status=StreamSignStatus.DRAFT,
        approval_depth=1,
        upstream_stream_id=source.stream_id,
        upstream_equipment_type=_upstream_equipment_type(source_type),
        stream_properties_json=dict(properties),
        composition_json=source.composition_json,
        # 物理量透传（如源流有）
        temp=source.temp,
        press=source.press,
        mass_flow=source.mass_flow,
        molar_flow=source.molar_flow,
        vapor_fraction=None,  # 由 flash_persist 后续按需更新
    )
    db.add(outlet)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise
    return outlet


__all__ = [
    "OutletStreamProjectMismatchError",
    "OutletSourceType",
    "create_outlet_stream",
]
