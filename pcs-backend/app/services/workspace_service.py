"""WorkspaceService（Sprint 1）。

CRUD + 自动清理 + 物理删除顺序：
1. 该 workspace 下所有记录（piping_results 等）的 snapshot
2. workspace
4. ARQ 任务以 7/90 天保留期清理 TEMPORARY/PERSONAL 超期 workspace
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, WorkspaceType
from app.models.project import Workspace
from app.services.audit_service import AuditService


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        workspace_type: WorkspaceType,
        name: str,
        project_id: uuid.UUID | None = None,
        retention_days: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> Workspace:
        """创建 workspace。

        - retention_days 默认按 workspace_type 派生：FORMAL=None（永久）/ PERSONAL=90 / TEMPORARY=7
        - 显式入参 retention_days 优先于派生默认值
        - last_active_at = 创建时刻（UTC）
        - 写 Audit WORKSPACE_CREATED（detail 含 workspace_type + name）
        - 不主动 commit，flush 后由调用方负责
        """
        if retention_days is None:
            retention_days = {"FORMAL": None, "PERSONAL": 90, "TEMPORARY": 7}[
                workspace_type.value
            ]
        ws = Workspace(
            workspace_type=workspace_type.value,
            owner_id=owner_id,
            project_id=project_id,
            name=name,
            retention_days=retention_days,
            last_active_at=datetime.now(UTC),
        )
        self.session.add(ws)
        await self.session.flush()
        await self.audit.write(
            action=AuditAction.WORKSPACE_CREATED,
            resource_type="workspaces",
            resource_id=ws.workspace_id,
            user_id=user_id,
            detail={"workspace_type": workspace_type.value, "name": name},
        )
        return ws

    async def get(self, workspace_id: uuid.UUID) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.workspace_id == workspace_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self, owner_id: uuid.UUID | None = None, limit: int = 100, offset: int = 0
    ) -> list[Workspace]:
        """按 owner_id 列 workspace（可全量）。

        - 默认 limit=100, offset=0（分页）
        - owner_id=None 视为不过滤（admin 用），否则按 owner_id 过滤
        - 排序依赖 PK（无显式 order_by，结果顺序由 PG 默认）

        对应 create_workspace：owner 字段写入 user_id（创建者即 owner）。
        """
        stmt = select(Workspace).limit(limit).offset(offset)
        if owner_id is not None:
            stmt = stmt.where(Workspace.owner_id == owner_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def import_records(
        self,
        *,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> int:
        """占位：P0 无 record 实体；后续 Sprint 实际复制 piping_results。"""
        ws = await self.get(workspace_id)
        if ws is None:
            raise ValueError("workspace not found")
        ws.project_id = project_id
        ws.last_active_at = datetime.now(UTC)
        await self.session.flush()
        record_count = 0
        await self.audit.write(
            action=AuditAction.WORKSPACE_IMPORTED,
            resource_type="workspaces",
            resource_id=workspace_id,
            user_id=user_id,
            detail={"project_id": str(project_id)},
        )
        return record_count

    async def touch(self, workspace_id: uuid.UUID) -> None:
        """更新 workspace.last_active_at（最近活跃时间戳，追踪 user 活跃）。

        步骤：
        1. UPDATE Workspace SET last_active_at=now() WHERE workspace_id=?
        2. 不主动 flush（依赖外层 commit 串行化）
        3. 用于 /workspaces/{workspace_id}（get_workspace）等读端点的活跃追踪

        与 list_for_user 区别：touch 单条更新（写）；list_for_user 列表（读）。
        """
        await self.session.execute(
            update(Workspace)
            .where(Workspace.workspace_id == workspace_id)
            .values(last_active_at=datetime.now(UTC))
        )

    async def cleanup_expired(self) -> int:
        """清理过期 PERSONAL/TEMPORARY workspace（系统任务调用）。"""
        now = datetime.now(UTC)
        count = 0
        ws_list = (
            await self.session.execute(
                select(Workspace).where(Workspace.retention_days.is_not(None))
            )
        ).scalars().all()
        for ws in ws_list:
            anchor = ws.last_active_at or ws.created_at
            if anchor is None:
                continue
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=UTC)
            if ws.retention_days is None:
                continue
            expires_at = anchor + timedelta(days=ws.retention_days)
            if expires_at <= now:
                await self.session.execute(
                    delete(Workspace).where(Workspace.workspace_id == ws.workspace_id)
                )
                await self.audit.write(
                    action=AuditAction.WORKSPACE_CLEANED,
                    resource_type="workspaces",
                    resource_id=ws.workspace_id,
                    user_id=None,
                    detail={"reason": "retention_expired", "retention_days": ws.retention_days},
                )
                count += 1
        await self.session.flush()
        return count