"""记录编辑审计读端点（TODO-066 · P9B-2 · T1）。

## 授权链（为什么授权靠**记录**不靠审计行）

```
请求 module + record_id
  → resolve_record_model(module, need_mixin=False)   # 未知模块 ⇒ 422
  → 取记录行                                       # 不存在 ⇒ 404
  → 项目守卫（记录的项目 ⇒ check_project_access_or_404）  # 别人项目 ⇒ 404
  → 按 resource_type=module + resource_id=record_id 查审计
```

⚠️ **`audit_logs` 表没有 `project_id`** ⇒ 审计行**自己**不带项目 ⇒
只能「先取记录（记录带 project_id）→ 用记录的项目做守卫 → 再按记录 id 查审计」。

⚠️ **只认 `action = RECORD_EDITED`**（ADR-0048 §⑦ 强制）—— 不得用
「该记录最近一条审计」泛匹配去凑。

⚠️ **不需要 9 态列**（`need_mixin=False`）：编辑历史对**任何有归属项目**的
记录都开放 —— 没有 `sign_status` 的表（如 `cost_est_results`）也能查它改过什么。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1.records_actions import _load_record
from app.db.session import get_db
from app.models.enums import AuditAction
from app.models.system import AuditLog
from app.schemas.record_edits import RecordEditItem, RecordEditsResponse

router = APIRouter(tags=["records"])

#: 与批注同口径：能读记录的人就能看它的编辑历史。
_READ_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")


@router.get(
    "/records/{module}/{record_id}/edits",
    response_model=RecordEditsResponse,
    summary="列记录的编辑审计（按项目守卫）",
)
async def list_record_edits(
    module: str,
    record_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> RecordEditsResponse:
    """列一条记录的编辑历史，最新在前。

    ⚠️ **只认 `action = RECORD_EDITED`**（ADR-0048 §⑦ 强制）—— 不得用
    「该记录最近一条审计」泛匹配去凑。
    """
    require_roles(actor, *_READ_ROLES)
    # need_mixin=False：编辑历史对**任何有归属项目**的记录都开放
    # （没有 sign_status 的表也能查它改过什么）。
    await _load_record(
        db, module=module, record_id=record_id, actor=actor, need_mixin=False
    )
    conditions = [
        AuditLog.action == AuditAction.RECORD_EDITED.value,
        AuditLog.resource_type == module,
        AuditLog.resource_id == str(record_id),
    ]
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = (
        await db.execute(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.audit_id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items: list[RecordEditItem] = []
    for row in rows:
        # ⚠️ 列名是 **`detail_json`**（`app/models/system.py` 的 `AuditLog`）——
        #    **不是** `detail`（照抄成 `row.detail` ⇒ AttributeError）。
        detail = row.detail_json if isinstance(row.detail_json, dict) else {}
        fields = detail.get("changed_fields")
        items.append(
            RecordEditItem(
                audit_id=row.audit_id,
                changed_fields=[str(f) for f in fields] if isinstance(fields, list) else [],
                overwrote_stale_baseline=bool(detail.get("overwrote_stale_baseline", False)),
                user_id=row.user_id,
                occurred_at=row.occurred_at,
            )
        )
    return RecordEditsResponse(
        record_type=module, record_id=record_id, items=items, total=int(total or 0)
    )
