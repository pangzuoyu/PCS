"""编辑审计读端点的响应（TODO-066 · P9B-2 · T1）。

## 为什么需要它

SPEC §6.21 P9A-LCK-006 要求 409 弹窗提供「查看差异」，而差异内容在**编辑审计**
里（`audit_logs` 的 `RECORD_EDITED`）。但唯一的读端点 `GET /audit-logs`
**限 SYSTEM_ADMIN** ⇒ 普通 DESIGNER 拿到冲突弹窗却**点不开差异**。

⚠️ **`audit_logs` 表没有 `project_id`** ⇒ 授权只能靠
「`resource_type` + `resource_id` → 反查记录 → 记录的项目」。

## `changed_fields` 是**字段名列表**，不是值

一次大改版几十 KB，审计里只记字段名（ADR-0048 §⑦）。本端点**原样透传**，
**不**去回查旧值 —— 回查旧值需要快照表，而那是另一个设计（TODO）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RecordEditItem(BaseModel):
    """一次编辑。"""

    audit_id: uuid.UUID
    changed_fields: list[str] = Field(
        default_factory=list, description="被改的字段名列表（不是值）"
    )
    overwrote_stale_baseline: bool = Field(
        default=False,
        description="这次编辑是否覆盖了无法校验的基线（ADR-0048 §⑦ 的额外审计行）",
    )
    user_id: uuid.UUID | None = Field(default=None, description="操作人；系统动作为空")
    occurred_at: datetime


class RecordEditsResponse(BaseModel):
    """一条记录的编辑历史。"""

    record_type: str = Field(description="RECORD_TYPE_REGISTRY 的键")
    record_id: uuid.UUID
    items: list[RecordEditItem]
    total: int
