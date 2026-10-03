"""Workspace API（Sprint 1）。

POST /workspaces/import 已推迟到 P1.2（设计缺陷6裁决）。

F-P3-003 Sprint 3: PATCH /workspaces/{workspace_id}/archive 端点（SYSTEM_ADMIN）。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1._guard import check_project_access_or_404
from app.db.session import get_db
from app.models.enums import WorkspaceStatus, WorkspaceType
from app.models.project import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut
from app.services.advisory_lock import acquire_record_lock
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=http_status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    owner_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    """创建工作区（POST /workspaces，201 Created）。

    步骤：
    1. 构造 WorkspaceService，传入当前 session
    2. 调 svc.create：owner_id（=user_id）、workspace_type（来自 payload
       枚举字符串）、name、project_id（None 表个人工作区）、retention_days
    3. service 层已 flush 不 commit（WorkspaceService.create 契约）；此处补
       session.commit() 落库
    4. 转 WorkspaceOut 返回（含 id/name/type/project_id/retention_days/
       created_by/created_at 等字段）

    owner_id 来自 Depends（认证中间件注入），user_id 复用 owner_id：
    工作区拥有者即创建者。
    """
    svc = WorkspaceService(session)
    ws = await svc.create(
        owner_id=owner_id,
        workspace_type=WorkspaceType(payload.workspace_type),
        name=payload.name,
        project_id=payload.project_id,
        retention_days=payload.retention_days,
        user_id=owner_id,
    )
    await session.commit()
    return WorkspaceOut.model_validate(ws)


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    owner_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[WorkspaceOut]:
    """GET 列出工作区。

    步骤：
    1. 可选 query: owner_id（按 owner 过滤；不传 → 全部）
    2. 转发 WorkspaceService.list_for_user → 按 owner_id 过滤 + 分页
    3. ORM 行 → WorkspaceOut 序列化（FastAPI response_model 控制）

    无 ACL 校验：作为内部管理端点（admin 视图），不做角色限制。
    与 /workspaces/{workspace_id}（get_workspace）区别：本端点列表；
    get_workspace 单条 + touch + 404。
    """
    svc = WorkspaceService(session)
    rows = await svc.list_for_user(owner_id=owner_id)
    return [WorkspaceOut.model_validate(r) for r in rows]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    """GET 单个 workspace（按 ID）+ 更新 last_accessed_at。

    步骤：
    1. WorkspaceService.get 取行；不存在 → 404 workspace not found
    2. WorkspaceService.touch 写 last_accessed_at = now（活跃审计）
    3. session.commit() 落库
    4. ORM 行经 WorkspaceOut.model_validate 转响应 schema

    注意：本端点不要求 ACL（workspace_id 自身是访问令牌语义）；
    业务写操作请改用 api/deps.py require_formal_workspace 依赖。
    """
    svc = WorkspaceService(session)
    ws = await svc.get(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    await svc.touch(workspace_id)
    await session.commit()
    return WorkspaceOut.model_validate(ws)


@router.patch("/{workspace_id}/archive", response_model=WorkspaceOut)
async def archive_workspace(
    workspace_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    session: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    """归档 workspace (F-P3-003 Sprint 3 / Issue 2 校准).

    PATCH /workspaces/{workspace_id}/archive — 改 status='ARCHIVED', 不删数据.

    ACL: SYSTEM_ADMIN. archive 后 FK RESTRICT 允许显式删 (但当前无 DELETE 端点).

    D2 2A 模式: 同 workspace_id 串行 archive (advisory lock), 防并发竞态.
    与 PCS 已用 advisory_lock.py 模式一致 (sync_from_source.actor 等).

    幂等: 重复归档返回 200 (不报 409), 避免误判.
    """
    require_roles(user, "SYSTEM_ADMIN")
    # D2 2A: 事务级 advisory lock (同 workspace_id 串行 archive, 防并发竞态).
    # 复用 advisory_lock.acquire_record_lock (classid/objid 双参, PG+SQLite 兼容).
    await acquire_record_lock(
        session, record_table="workspaces", record_id=str(workspace_id)
    )
    record = (
        await session.execute(
            select(Workspace).where(Workspace.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    # P7-7+ BLOCKER-3 关键 endpoint 集成 check_project_access (SYSADMIN 自动通过, 留 audit)
    if record is not None and record.project_id is not None:
        await check_project_access_or_404(
            session,
            user_id=user.user_id,
            project_id=record.project_id,
            actor_roles=[user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role],
        )
    if record is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if record.status == WorkspaceStatus.ARCHIVED.value:
        # 幂等返回 (避免 409 误判)
        return WorkspaceOut.model_validate(record)
    record.status = WorkspaceStatus.ARCHIVED.value
    await session.commit()
    await session.refresh(record)
    return WorkspaceOut.model_validate(record)