"""ChecklistService（Sprint 1）。

DICT-ALL-003 V3.1 表44：5态校验 + completeness 计算。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.models.system import ProjectInputChecklist
from app.schemas.checklist import ChecklistCompleteness, ChecklistItemCreate, ChecklistItemPut
from app.services.audit_service import AuditService


class ChecklistService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def list_for_project(self, project_id: uuid.UUID) -> list[ProjectInputChecklist]:
        stmt = (
            select(ProjectInputChecklist)
            .where(ProjectInputChecklist.project_id == project_id)
            .order_by(ProjectInputChecklist.item_key)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def bulk_seed(
        self,
        *,
        project_id: uuid.UUID,
        items: list[ChecklistItemCreate],
        user_id: uuid.UUID | None = None,
    ) -> list[ProjectInputChecklist]:
        created: list[ProjectInputChecklist] = []
        for it in items:
            row = ProjectInputChecklist(
                project_id=project_id,
                item_key=it.item_key,
                item_label=it.item_label,
                required=it.required,
                note=it.note,
                module=it.module,
                input_category=it.input_category,
                status="NOT_STARTED",
            )
            self.session.add(row)
            created.append(row)
        await self.session.flush()
        return created

    async def update_status(
        self,
        *,
        checklist_id: uuid.UUID,
        payload: ChecklistItemPut,
        user_id: uuid.UUID | None = None,
    ) -> ProjectInputChecklist:
        stmt = select(ProjectInputChecklist).where(
            ProjectInputChecklist.checklist_id == checklist_id
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError("checklist item not found")
        row.status = payload.status
        row.input_value_json = payload.input_value_json
        row.source_type = payload.source_type
        row.assumption_reason = payload.assumption_reason
        if payload.status == "VERIFIED":
            row.verified_by = user_id
            row.verified_at = datetime.now(UTC)
        elif payload.status in ("NOT_STARTED", "IN_PROGRESS"):
            row.verified_by = None
            row.verified_at = None
        await self.session.flush()
        action = (
            AuditAction.CHECKLIST_ITEM_VERIFIED
            if payload.status == "VERIFIED"
            else AuditAction.CHECKLIST_ITEM_ASSUMED
            if payload.status == "ASSUMED"
            else AuditAction.READ
        )
        await self.audit.write(
            action=action,
            resource_type="project_input_checklist",
            resource_id=checklist_id,
            user_id=user_id,
            detail={"new_status": payload.status},
        )
        return row

    async def completeness(self, project_id: uuid.UUID) -> ChecklistCompleteness:
        items = await self.list_for_project(project_id)
        # DICT V3.1：以 input_category==REQUIRED 判定（旧 P0 required bool 兼容）
        required_items = [
            i
            for i in items
            if i.input_category == "REQUIRED" or (i.required and not i.input_category)
        ]
        total = len(items)
        req_total = len(required_items)
        req_verified = sum(1 for i in required_items if i.status == "VERIFIED")
        req_assumed = sum(1 for i in required_items if i.status == "ASSUMED")
        req_blocked = sum(
            1 for i in required_items if i.status in ("NOT_STARTED", "IN_PROGRESS")
        )
        pct = (
            100.0 * (req_verified + req_assumed) / req_total if req_total else 100.0
        )
        return ChecklistCompleteness(
            project_id=project_id,
            total=total,
            required_total=req_total,
            required_verified=req_verified,
            required_assumed=req_assumed,
            required_blocked=req_blocked,
            completeness_pct=round(pct, 2),
        )


async def count_assumed_for_project(session: AsyncSession, project_id: uuid.UUID) -> int:
    stmt = select(func.count(ProjectInputChecklist.checklist_id)).where(
        ProjectInputChecklist.project_id == project_id,
        ProjectInputChecklist.required.is_(True),
        ProjectInputChecklist.status == "ASSUMED",
    )
    return int((await session.execute(stmt)).scalar_one())