"""物流「校核记录」的响应契约（TODO-112 · P9B-4 紧急批次 T6）。

⚠️ **具名 schema** —— 不是裸 dict ⇒
- 前端类型可**契约派生**（`components['schemas']['ReviewLogItem']`）；
- `check_openapi_payload_coverage.py` 的**裸载荷数不涨**（基线 71）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewLogItem(BaseModel):
    """一条校核记录（一次校对相关状态转移）。"""

    transition: str = Field(
        description="状态转移名：SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK"
    )
    operator: str | None = Field(
        default=None, description="操作人 user_id（审计里的 actor）"
    )
    occurred_at: str = Field(description="发生时间（ISO 8601）")
    detail: str | None = Field(default=None, description="附加说明（如驳回理由）")
