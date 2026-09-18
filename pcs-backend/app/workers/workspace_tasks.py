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
    """旧 ctx 兼容 wrapper：直接接收 session，调用 WorkspaceService.cleanup_expired。

    业务：兼容旧 ARQ 任务签名（session 直传而非 ctx dict）；
    返回删除行数（caller 通常忽略）。
    """
    svc = WorkspaceService(session)
    return await svc.cleanup_expired()


def _now() -> datetime:
    """当前 UTC 时间（ARQ worker 任务上下文时间戳统一）。"""
    return datetime.now(UTC)