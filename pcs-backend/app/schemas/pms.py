"""PMS 管道材料规格的请求/响应契约（P10-H · T2 · TODO-195）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: 危险等级（前端 `types/pms.ts` 的 `HazardLevel` 字面量）。
HazardLevel = Literal["LOW", "MEDIUM", "HIGH"]


class PmsItemBase(BaseModel):
    """PMS 条目的业务字段（新建 / 修改共用）。"""

    model_config = ConfigDict(extra="forbid")

    pms_no: str = Field(..., min_length=1, max_length=40, description="PMS 编号（项目内唯一）")
    description: str = Field(
        default="", max_length=300, description="描述"
    )
    pms_class: str = Field(
        default="", max_length=40, description="材料等级 / 类别"
    )
    hazard_level: HazardLevel = Field(
        default="LOW", description="危险等级（驱动审批层级）"
    )


class PmsItemCreate(PmsItemBase):
    """`POST /projects/{project_id}/pms` 请求体。"""

    model_config = ConfigDict(extra="forbid")


class PmsItemUpdate(PmsItemBase):
    """`PATCH /projects/{project_id}/pms/{item_id}` 请求体。"""


class PmsItemResponse(BaseModel):
    """`PmsItem` 响应（`GET` 列表 / 详情 / `POST` / `PATCH`）。"""

    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    project_id: uuid.UUID
    pms_no: str
    description: str
    pms_class: str
    hazard_level: str
    sign_status: str = Field(..., description="记录门禁 9 态（RecordSignStatus9）")
    record_hash: str = Field(default="", description="内容哈希（16 hex）")
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PmsItemListResponse(BaseModel):
    """`GET /projects/{project_id}/pms` 响应。"""

    items: list[PmsItemResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0
