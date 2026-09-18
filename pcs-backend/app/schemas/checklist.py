"""ProjectInputChecklist Pydantic schemas（Sprint 1）。

DICT-ALL-003 V3.1 表44：5态 status + source_type + verified_by/verified_at +
assumption_reason + input_category + input_value_json。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChecklistItemCreate(BaseModel):
    item_key: str = Field(
        ..., min_length=1, max_length=100, description="校验项键名（项目内唯一）"
    )
    item_label: str = Field(
        ..., min_length=1, max_length=200, description="校验项显示名"
    )
    module: str | None = Field(
        default=None, max_length=30, description="所属模块（如 STREAM/EQUIP/PIPING）"
    )
    input_category: str | None = Field(
        default=None,
        pattern="^(REQUIRED|CONDITIONAL|OPTIONAL)$",
        description="输入类别：REQUIRED 必填 / CONDITIONAL 有条件 / OPTIONAL 选填",
    )
    required: bool = Field(True, description="是否必填校验")
    note: str | None = Field(None, description="备注说明")


class ChecklistItemPut(BaseModel):
    """PUT 校验一项（5态 + 元数据）。"""

    status: str = Field(
        ...,
        pattern="^(NOT_STARTED|IN_PROGRESS|VERIFIED|ASSUMED|NOT_APPLICABLE)$",
        description=(
            "校验状态 5 态：NOT_STARTED 未开始 / IN_PROGRESS 进行 / "
            "VERIFIED 已核 / ASSUMED 假设 / NOT_APPLICABLE 不适用"
        ),
    )
    input_value_json: dict | None = Field(None, description="实际输入值 JSON")
    source_type: str | None = Field(
        default=None,
        max_length=20,
        description="来源类型：DESIGN_DOC/LAB_REPORT/VENDOR_DATA/ENGINEER_ASSUMPTION",
    )
    assumption_reason: str | None = Field(None, description="假设原因（status=ASSUMED 时必填）")


class ChecklistItemOut(BaseModel):
    checklist_id: uuid.UUID = Field(..., description="校验项 ID")
    project_id: uuid.UUID = Field(..., description="所属项目 ID")
    item_key: str = Field(..., description="校验项键名")
    item_label: str = Field(..., description="校验项显示名")
    module: str | None = Field(None, description="所属模块")
    input_category: str | None = Field(None, description="输入类别")
    required: bool = Field(..., description="是否必填校验")
    input_value_json: dict | None = Field(None, description="实际输入值 JSON")
    source_type: str | None = Field(None, description="来源类型")
    status: str = Field(..., description="校验状态 5 态")
    verified_by: uuid.UUID | None = Field(None, description="校验人 ID")
    verified_at: datetime | None = Field(None, description="校验时间")
    assumption_reason: str | None = Field(None, description="假设原因")
    note: str | None = Field(None, description="备注说明")

    model_config = {"from_attributes": True}


class ChecklistCompleteness(BaseModel):
    project_id: uuid.UUID = Field(..., description="项目 ID")
    total: int = Field(..., description="校验项总数")
    required_total: int = Field(..., description="必填项数")
    required_verified: int = Field(..., description="必填已校验数")
    required_assumed: int = Field(..., description="必填已假设数（ASSUMED 视同通过）")
    required_blocked: int = Field(..., description="必填阻塞数（NOT_STARTED/IN_PROGRESS）")
    completeness_pct: float = Field(..., description="完整度百分比 0~100")  # 0~100


class ChecklistBulkSeed(BaseModel):
    """批量预置：种子脚本/一次性导入使用。"""

    items: list[ChecklistItemCreate] = Field(..., description="批量预置条目列表")