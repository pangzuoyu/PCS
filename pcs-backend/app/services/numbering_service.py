"""NumberingService — 文档编号原子自增 + UNIQUE 约束防并发（Task 2.7）。

SELECT ... FOR UPDATE 行锁串行化同 scope 的并发 + UNIQUE 约束兜底。
写 audit：reset() 必须留痕（counter 被人重置是高敏操作）。

实现注意（与 brief 偏差，防御性）：
1. 补全 brief 缺失的 `AsyncSession` import（brief 仅 import `from sqlalchemy import select`）。
2. `reset()` 在 composite resource_id 超过 100 字符时由 AuditService 自动截断
   （audit_service.py:52）；UUID 36 + "/" + 36 + "/" + scope_key<=50 = 124 上限，
   实际 scope_key 默认 "scope_A" (7 chars) → 81 chars，安全。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import DocNoSequence
from app.models.enums import AuditAction
from app.services.audit_service import AuditService


class SequenceNotFoundError(Exception):
    """查不到指定 DocNoSequence 时抛出。"""


class NumberingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def next_value(self, project_id: UUID, template_id: UUID, scope_key: str) -> int:
        # SELECT ... FOR UPDATE 行锁 — Postgres 串行化同 scope 的并发
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            row = DocNoSequence(
                project_id=project_id,
                template_id=template_id,
                scope_key=scope_key,
                current_value=0,
            )
            self.session.add(row)
            await self.session.flush()
        row.current_value += 1
        await self.session.flush()
        return row.current_value

    async def reset(self, project_id, template_id, scope_key, *, new_value=0, actor: UUID) -> None:
        row = (await self.session.execute(
            select(DocNoSequence).where(
                DocNoSequence.project_id == project_id,
                DocNoSequence.template_id == template_id,
                DocNoSequence.scope_key == scope_key,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is None:
            raise SequenceNotFoundError(f"未找到 scope={scope_key}")
        row.current_value = new_value
        await self.session.flush()
        await self.audit.write(
            user_id=actor,
            action=AuditAction.CONFIG_VERSION_CREATED,
            resource_type="doc_no_sequence",
            resource_id=f"{project_id}/{template_id}/{scope_key}",
        )