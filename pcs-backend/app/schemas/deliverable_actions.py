"""`GET /deliverables/{id}/actions` 的响应 schema（P9A B4d）。

## 为什么 `detail_json` 是 JSON **文本**而不是 `dict`

审计的 `detail_json` 结构**随 action 而变**（签发带 rev/doc_no，签署带
step_role/decision，代录带 approver_name/file_hash）。铺平成 `dict` 会让
OpenAPI 里出现一个无属性的 object —— 那正是 P9A-DLV-010 的裸字段
（基线 71，只拦倒退），也会让前端每次自己猜结构。

⇒ 序列化成紧凑 JSON 文本暴露：契约里它明确是 `string`，前端一次
`JSON.parse` 即可，而「结构随 action 变」这件事不会变成第二个真相源。
要真正类型化，得先让各 action 的 detail 结构固定下来 —— 那是 P9B 的事。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeliverableActionResponse(BaseModel):
    """一条动作（= 一条审计记录）。

    字段集合被 `test_item_model_declares_every_field` 钉死 ——
    加字段要同时改那个测试，这是刻意的：契约变化必须是显式动作。
    """

    model_config = ConfigDict(from_attributes=True)

    action: str = Field(description="AuditAction 值，如 DELIVERABLE_ISSUED")
    resource_type: str = Field(
        description="deliverable（交付物级动作）/ deliverable_version（版本级动作）"
    )
    resource_id: str = Field(description="动作对象 ID（交付物 ID 或版本 ID）")
    actor_user_id: uuid.UUID | None = Field(default=None, description="操作人；系统动作为空")
    detail_json: str | None = Field(
        default=None, description="审计 detail_json 的 JSON 文本；结构随 action 而变"
    )
    created_at: datetime | None = None


class DeliverableActionsListResponse(BaseModel):
    """动作时间线。"""

    deliverable_id: uuid.UUID
    items: list[DeliverableActionResponse]
    total: int
