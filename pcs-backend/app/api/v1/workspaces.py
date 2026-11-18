"""Workspace API（Sprint 1）。

POST /workspaces/import 已推迟到 P1.2（设计缺陷6裁决）。

F-P3-003 Sprint 3: PATCH /workspaces/{workspace_id}/archive 端点（SYSTEM_ADMIN）。

⚠️ **P10-F · F3（TODO-186）**：本模块的三个端点此前**不要求登录**
⇒ ⇒ 匿名可枚举**全部**工作区（`owner_id` 不传即全量）⇒ ⇒ 匿名 GET 还**写库**
（`touch`）⇒ ⇒ 匿名 POST 可指定**任意 `owner_id`** ⇒ ⇒ **审计行也记在那个
owner 名下**（审计污染）⇒ ⇒ ⇒ 现在：**要登录** + **要授权**。
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
from app.services.exceptions import WorkspaceNotFoundError
from app.services.workspace_service import (
    WorkspaceService,
    require_workspace_access_or_404,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=http_status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    user: Annotated[_Actor, Depends(current_actor)],
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

    ⚠️ **P10-F · F3（TODO-186）**：**要登录** + **`owner_id` 必须是令牌里的那个人**
    ⇒ ⇒ 理由：原来 `owner_id` 由客户端任意填 ⇒ ⇒ 建的行的 owner 是别人
    ⇒ ⇒ ⇒ 而 `WorkspaceService.create` 把 `user_id=owner_id` 写进
    **`WORKSPACE_CREATED` 审计行** ⇒ ⇒ ⇒ **匿名可把审计行记在别人名下**
    ⇒ ⇒ ⇒ 「替别人建工作区」这件事**不在**这里开放
    （⇒ ⇒ 那是 `POST /projects` 的产品语义 · TODO-175）。
    """
    if owner_id != user.user_id:
        raise HTTPException(
            status_code=403, detail="owner_id must match the current user"
        )
    svc = WorkspaceService(session)
    ws = await svc.create(
        owner_id=user.user_id,
        workspace_type=WorkspaceType(payload.workspace_type),
        name=payload.name,
        project_id=payload.project_id,
        retention_days=payload.retention_days,
        user_id=user.user_id,
    )
    await session.commit()
    return WorkspaceOut.model_validate(ws)


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: Annotated[_Actor, Depends(current_actor)],
    owner_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[WorkspaceOut]:
    """GET 列出工作区。

    步骤：
    1. 可选 query: owner_id（按 owner 过滤）
    2. 转发 WorkspaceService.list_for_user → 按 owner_id 过滤 + 分页
    3. ORM 行 → WorkspaceOut 序列化（FastAPI response_model 控制）

    ⚠️ **P10-F · F3（TODO-186）**：**要登录** + **两种模式**：

    | `owner_id` | 谁能调 |
    |---|---|
    | **= 令牌里的那个人** | 任何人（列**自己的**） |
    | **别人的 / 不传** | **仅 `SYSTEM_ADMIN`**（= 前端注释里说的「admin 视图」） |

    ⇒ ⇒ 理由：原来**不传 `owner_id` 就是全量**、且**不要求登录**
    ⇒ ⇒ ⇒ 匿名可枚举**全部**工作区 ⇒ ⇒ 而 `workspace_id` 正是
    `records.py` 读端点的钥匙（TODO-179）⇒ ⇒ ⇒ 两条是一条链。
    """
    is_admin = "SYSTEM_ADMIN" in list(user.roles)
    if owner_id is None or owner_id != user.user_id:
        if not is_admin:
            raise HTTPException(
                status_code=403,
                detail="listing other users' workspaces requires SYSTEM_ADMIN",
            )
    svc = WorkspaceService(session)
    rows = await svc.list_for_user(owner_id=owner_id)
    return [WorkspaceOut.model_validate(r) for r in rows]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    session: AsyncSession = Depends(get_db),
) -> WorkspaceOut:
    """GET 单个 workspace（按 ID）+ 更新 last_accessed_at。

    步骤：
    1. WorkspaceService.get 取行；不存在 → 404 workspace not found
    2. **授权判定**（TODO-186）⇒ ⇒ 无权 ⇒ ⇒ **404**（与「不存在」同形）
    3. WorkspaceService.touch 写 last_accessed_at = now（活跃审计）
    4. session.commit() 落库
    5. ORM 行经 WorkspaceOut.model_validate 转响应 schema

    ⚠️ **P10-F · F3（TODO-186）**：本端点此前**不要求登录、也没有 ACL**
    ⇒ ⇒ **且 `touch` 是写副作用** ⇒ ⇒ 匿名 GET ⇒ ⇒ **匿名写库**
    ⇒ ⇒ ⇒ 现在：**要登录** + **要对该工作区有访问权**
    ⇒ ⇒ ⇒ 「无权」与「不存在」抛**同一个** `WorkspaceNotFoundError`
    ⇒ ⇒ ⇒ 响应**逐字相同** ⇒ ⇒ ⇒ 枚举不出 UUID。
    """
    svc = WorkspaceService(session)
    ws = await svc.get(workspace_id)
    if ws is None:
        # ⚠️ **与「无权」抛的是同一个异常**（`WorkspaceNotFoundError`）
        # ⇒ ⇒ 「不存在」与「无权」⇒ ⇒ **逐字同形** ⇒ ⇒ 枚举不出 UUID
        # ⇒ ⇒ （此前这里是 `HTTPException` ⇒ ⇒ code 与守卫那份不同 ⇒ ⇒ 可区分）
        raise WorkspaceNotFoundError(
            f"workspace_id={workspace_id} not found",
            details={"workspace_id": str(workspace_id)},
        )
    await require_workspace_access_or_404(
        session, workspace=ws, user_id=user.user_id, actor_roles=list(user.roles)
    )
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
    # P7-7+ BLOCKER-3 关键 endpoint 集成 check_project_access (SYSTEM_ADMIN bypass)
    if record is not None and record.project_id is not None:
        await check_project_access_or_404(
            session,
            user_id=user.user_id,
            project_id=record.project_id,
            actor_roles=list(user.roles),
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