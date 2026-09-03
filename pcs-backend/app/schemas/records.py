"""Record 通用 Pydantic schemas（Sprint 2）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import RecordSignStatus9, StateTransition


class RecordTransitionRequest(BaseModel):
    transition: StateTransition
    reason: str | None = None


class RecordResponse(BaseModel):
    """最小响应：sign_status + audit 关键字段。"""

    record_type: str
    record_id: uuid.UUID
    sign_status: RecordSignStatus9
    approval_step: int | None
    locked_by_deliverable: bool
    changed_at: datetime | None = None
    detail: dict[str, Any] | None = None