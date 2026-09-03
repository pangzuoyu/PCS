"""AuditService：审计统一入口（Issue 6 锁定）。

利用 P0 audit_logs 已有字段（user_id / action / resource_type / resource_id /
detail_json / occurred_at）承载 P1 Issue 6 语义：

- user_id       → actor（系统任务传 None）
- resource_type → 模块名（如 "piping_results" / "STATE_MACHINE" / "CIA"）
- resource_id   → 实体主键字符串（UUID 形式）
- detail_json   → 旧/新值、原因、sign_role/sign_step、ip/ua 等元数据
- occurred_at   → DB 自动 server_default=func.now()

零 Schema 变更。Sprint 2 状态机 / Sprint 3 CIA / 工作区清理 / 输入清单 统一走本类。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.models.system import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def write(
        self,
        *,
        action: AuditAction,
        resource_type: str,
        resource_id: str | uuid.UUID | None,
        user_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditLog:
        """写一条审计记录。

        Args:
            action: AuditAction 枚举
            resource_type: 模块名（"piping_results" / "STATE_MACHINE" / "WORKSPACE"）
            resource_id: 实体主键字符串
            user_id: 触发者（系统任务传 None）
            detail: 元数据 dict（old/new value / reason / sign_role 等）
        """
        entry = AuditLog(
            user_id=user_id,
            action=action.value,
            resource_type=resource_type[:50],
            resource_id=str(resource_id)[:100] if resource_id is not None else None,
            detail_json=detail,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry