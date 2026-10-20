"""workflow_progress 读 API 的响应 schema（P9A B5 / SPEC P9A-OBS-003）。

P9B 的甘特图 / 进度条 / 超时告警都消费本响应。

## 为什么 5 态计数是**显式字段**而不是 `dict[str, int]`

甘特图按 5 态上色，缺一态前端要么画不出颜色、要么自己编一个颜色 ——
后者就是第二次真相源，正是 P8 治理掉的那类「词表不在契约里」。

同时 `counts: dict[str, int]` 在 OpenAPI 里是一个**无属性 object**，
即 P9A-DLV-010 的裸字段（基线 71，只拦倒退）⇒ 也会让基线上涨。
⇒ 5 个显式整数字段，`WorkflowProgressState` 的每个成员各一个，永不缺席（含 0）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowProgressItemResponse(BaseModel):
    """单条观测行。字段集合被 `test_item_model_fields_are_pinned` 钉死。"""

    model_config = ConfigDict(from_attributes=True)

    progress_id: uuid.UUID
    step_order: int
    step_role: str
    step_status: str = Field(description="PENDING/IN_PROGRESS/COMPLETED/SKIPPED/FAILED")
    started_at: datetime | None = None
    completed_at: datetime | None = Field(default=None, description="终态时间；超时告警按它算")
    assignee: uuid.UUID | None = None
    result_hash: str | None = None


class WorkflowProgressResponse(BaseModel):
    """一条工作流的节点进度（甘特图的横轴 = `items` 的 `step_order`）。"""

    workflow_type: str
    workflow_id: uuid.UUID
    project_id: uuid.UUID = Field(description="鉴权与多态查询都靠这一列")
    total: int
    # 5 态计数，恒定存在（含 0）。字段名 = 状态名的小写形式。
    pending: int
    in_progress: int
    completed: int
    skipped: int
    failed: int
    items: list[WorkflowProgressItemResponse]
