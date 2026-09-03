"""Workspace 异步任务（ARQ workers）。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.services.workspace_service import WorkspaceService


async def cleanup_expired_workspaces(ctx: dict) -> int:
    """清理过期 PERSONAL/TEMPORARY workspace。ARQ cron 触发。"""
    factory = ctx["session_factory"]
    async with factory() as session:
        svc = WorkspaceService(session)
        n = await svc.cleanup_expired()
        await session.commit()
        return n


async def touch_workspace(ctx: dict, workspace_id: str) -> bool:
    """更新指定 workspace last_active_at（活跃心跳）。"""
    factory = ctx["session_factory"]
    async with factory() as session:
        svc = WorkspaceService(session)
        await svc.touch(uuid.UUID(workspace_id))
        await session.commit()
        return True


# 兼容旧 ctx dict 直接传 session 的简易 helper
async def cleanup_with_session(session) -> int:
    svc = WorkspaceService(session)
    return await svc.cleanup_expired()


def _now() -> datetime:
    return datetime.now(UTC)