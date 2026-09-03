"""ARQ worker failure 路径测试：cleanup_expired_workspaces 应捕获并记录异常。"""

from __future__ import annotations

from datetime import UTC

import pytest

pytestmark = pytest.mark.asyncio


async def test_cleanup_expired_handles_empty_db(db_session):
    """空 DB 上 cleanup 应返回 0，不抛。"""
    from app.services.workspace_service import WorkspaceService

    svc = WorkspaceService(db_session)
    n = await svc.cleanup_expired()
    assert n == 0


async def test_cleanup_expired_removes_past_temporary(db_session):
    """超过 retention_days 的 TEMPORARY workspace 会被清理。"""
    import uuid
    from datetime import datetime, timedelta

    from app.models.enums import WorkspaceType
    from app.models.project import Workspace
    from app.services.workspace_service import WorkspaceService

    past = datetime.now(UTC) - timedelta(days=10)
    ws = Workspace(
        workspace_type=WorkspaceType.TEMPORARY.value,
        owner_id=uuid.uuid4(),
        name="expired",
        retention_days=7,
        last_active_at=past,
        created_at=past,
    )
    db_session.add(ws)
    await db_session.flush()
    ws_id = ws.workspace_id

    svc = WorkspaceService(db_session)
    n = await svc.cleanup_expired()
    await db_session.commit()
    assert n >= 1

    from sqlalchemy import select

    from app.models.project import Workspace as W

    found = (
        await db_session.execute(select(W).where(W.workspace_id == ws_id))
    ).scalar_one_or_none()
    assert found is None


async def test_worker_module_loads():
    """WorkerSettings 可导入并暴露函数列表（防 regression：误删 cleanup）。"""
    from app.workers import worker as worker_mod
    from app.workers.workspace_tasks import (
        cleanup_expired_workspaces,
        touch_workspace,
    )

    assert cleanup_expired_workspaces in worker_mod.WorkerSettings.functions
    assert touch_workspace in worker_mod.WorkerSettings.functions


async def test_touch_workspace_via_service(db_session):
    """touch_workspace task 入口（直接调用 service）。"""
    import uuid

    from app.models.enums import WorkspaceType
    from app.models.project import Workspace
    from app.services.workspace_service import WorkspaceService

    ws = Workspace(
        workspace_type=WorkspaceType.PERSONAL.value,
        owner_id=uuid.uuid4(),
        name="active",
        retention_days=90,
    )
    db_session.add(ws)
    await db_session.flush()
    svc = WorkspaceService(db_session)
    await svc.touch(ws.workspace_id)
    await db_session.commit()

    from sqlalchemy import select

    from app.models.project import Workspace as W

    row = (
        await db_session.execute(select(W).where(W.workspace_id == ws.workspace_id))
    ).scalar_one()
    assert row.last_active_at is not None