"""S1-4b EQUIP_LIST API schemas。

Per P7 SPEC V1.4 §3.2.1 + R8 ruling 补 API 层；与 sync_service (S1-4) 协同：
- sync_from_source (S1-4): 主入口，CHECKED 触发
- sync_request_body (本文件): 手动 trigger API
- bulk_sync_request_body: 批量 sync 入口

设计要点：
- Pydantic BaseModel 模式（沿用 equip_lib.py / pump.py）
- 不暴露业务计算字段（仅元信息 + V1.4 source_service）
- 字段命名与 EquipmentList ORM 1:1 映射
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EquipListSyncRequest(BaseModel):
    """手动触发 sync_from_source API body。

    业务：用户在前端 EquipmentListPage 点 "重新同步" 按钮 → POST 此 body
    → 后端调 sync_from_source → EquipmentList 记录更新（equipment_status="E"
    联动 + V1.4 source_service 字段写入）。
    """

    source_module: Literal[
        "PUMP", "VESSEL", "HEAT", "PSV", "CV",
        "COOL_TOWER", "PSYCHRO", "OPEN_CHANNEL",
    ] = Field(..., description="源模块（PUMP/VESSEL/HEAT/PSV/CV/COOL_TOWER/PSYCHRO/OPEN_CHANNEL）")
    source_service: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="源 service 名（如 pump_service / vessel_service）",
    )
    source_record_id: uuid.UUID = Field(..., description="源记录 PK（如 PumpResult.pump_id）")


class EquipListBulkSyncRequest(BaseModel):
    """批量 sync 入口。

    业务：项目初始化或 CHECKED 触发器重启后，批量拉取所有 source_module=...
    的 CHECKED 记录 → 同步到 EquipmentList。每个 entry 独立失败不影响其他。
    """

    entries: list[EquipListSyncRequest] = Field(
        ..., min_length=1, max_length=100, description="1-100 个 sync 条目"
    )


class EquipListListFilter(BaseModel):
    """GET /api/v1/equipment-list query params。

    业务：项目视图按 tag_number 前缀 / source_module / sign_status 过滤。
    """

    project_id: uuid.UUID | None = Field(None, description="按项目过滤")
    workspace_id: uuid.UUID | None = Field(None, description="按 workspace 过滤")
    source_module: str | None = Field(None, description="按源模块过滤")
    sign_status: str | None = Field(None, description="按签审状态过滤（DRAFT/CHECKED/STALE 等）")
    equipment_status: str | None = Field(
        None, description="按设备状态过滤（N=New/E=Existing/D=Deleted/M=Modified/F=Frozen）"
    )
    limit: int = Field(100, ge=1, le=500, description="返回数量上限 1-500")
    offset: int = Field(0, ge=0, description="分页 offset")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class EquipListResponse(BaseModel):
    """EquipmentList 单条记录 API 响应。

    字段命名 1:1 映射 EquipmentList ORM；含 V1.4 source_service。
    不含 calc_lineage / approval_detail 等深度字段（按需单独 GET）。
    """

    equipment_id: uuid.UUID
    equipment_type_project_id: uuid.UUID | None
    type_code: str
    equipment_name: str
    equipment_description: str | None = None
    tag_number: str | None = None
    vendor: str | None = None
    vendor_model: str | None = None
    source_module: str | None = None
    source_service: str | None = None  # V1.4 新增
    source_record_id: uuid.UUID | None = None
    procurement_status: str | None = None
    installation_location: str | None = None
    net_weight: float | None = None
    equipment_status: str
    sign_status: str
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: str | None = None
    updated_at: str | None = None


class EquipListListResponse(BaseModel):
    """EquipmentList 列表 API 响应（含分页元数据）。"""

    items: list[EquipListResponse]
    total: int = Field(..., description="满足过滤条件的总记录数（不含 limit/offset）")
    limit: int
    offset: int


class EquipListSyncResponse(BaseModel):
    """sync API 响应。

    Returns:
        EquipListResponse: 同步后的 EquipmentList 记录
        was_created: True=新建（equipment_status="N"）/ False=更新（equipment_status="E"）
    """

    item: EquipListResponse
    was_created: bool


class EquipListBulkSyncResponse(BaseModel):
    """批量 sync 响应：每条目 success / failure 分开报告。"""

    succeeded: list[EquipListSyncResponse] = Field(default_factory=list)
    failed: list[dict] = Field(
        default_factory=list,
        description="失败条目：{ entry, error_code, error_message }",
    )
