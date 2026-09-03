"""ProjectInputChecklist Pydantic schemas（Sprint 1）。

DICT-ALL-003 V3.1 表44：5态 status + source_type + verified_by/verified_at +
assumption_reason + input_category + input_value_json。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChecklistItemCreate(BaseModel):
    item_key: str = Field(min_length=1, max_length=100)
    item_label: str = Field(min_length=1, max_length=200)
    module: str | None = Field(default=None, max_length=30)
    input_category: str | None = Field(
        default=None, pattern="^(REQUIRED|CONDITIONAL|OPTIONAL)$"
    )
    required: bool = True
    note: str | None = None


class ChecklistItemPut(BaseModel):
    """PUT 校验一项（5态 + 元数据）。"""

    status: str = Field(
        ..., pattern="^(NOT_STARTED|IN_PROGRESS|VERIFIED|ASSUMED|NOT_APPLICABLE)$"
    )
    input_value_json: dict | None = None
    source_type: str | None = Field(default=None, max_length=20)
    assumption_reason: str | None = None


class ChecklistItemOut(BaseModel):
    checklist_id: uuid.UUID
    project_id: uuid.UUID
    item_key: str
    item_label: str
    module: str | None
    input_category: str | None
    required: bool
    input_value_json: dict | None
    source_type: str | None
    status: str
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    assumption_reason: str | None
    note: str | None

    model_config = {"from_attributes": True}


class ChecklistCompleteness(BaseModel):
    project_id: uuid.UUID
    total: int
    required_total: int
    required_verified: int
    required_assumed: int
    required_blocked: int
    completeness_pct: float  # 0~100


class ChecklistBulkSeed(BaseModel):
    """批量预置：种子脚本/一次性导入使用。"""

    items: list[ChecklistItemCreate]