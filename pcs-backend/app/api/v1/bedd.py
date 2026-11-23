"""BEDD 文档 API（P10-H · T2 · TODO-195 · SPEC §7.5）。

端点（挂 `/projects` 前缀）：

- `GET /api/v1/projects/{project_id}/bedd` —— 读（`projects.bedd_json`）
- `PUT /api/v1/projects/{project_id}/bedd` —— 写（**整份替换**）

## 为什么是「整份替换」而不是 PATCH

BEDD 是一份**结构固定的文档**（9 个分组 · 字段白名单）⇒ ⇒ 局部合并要处理
「删字段 / 改分组」两种语义 ⇒ ⇒ 而 UI 是「分组 Tab 编辑 ⇒ 保存」⇒ ⇒
**整份 PUT** 更简单也更不容易出半新半旧的状态。

⚠️ **那一列此前只有建表迁移提到它** ⇒ ⇒ **没有任何写入路径** ⇒ ⇒
补出来的读端点**永远返回空** ⇒ ⇒ 这个 PUT 就是那条缺失的写入路径。

ACL：读 = DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN；
写 = DESIGNER / SYSTEM_ADMIN（**数据源录入**⇒ ⇒ 审核角色不写）。
守卫：`check_project_access_or_404`（无权 ⇒ ⇒ **404**）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.project import Project
from app.schemas.bedd import BeddDocument, BeddResponse
from app.services.exceptions import PcsError

router = APIRouter(prefix="/projects", tags=["bedd"])

_READ_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
# ⚠️ **审核角色不写数据源**（REVIEWER / APPROVER 不在列）⇒ ⇒
#   但**工艺角色要能写**（公用工程 / 排放限值那几组是工艺填的）。
_WRITE_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")


async def _get_project(
    db: AsyncSession, project_id: uuid.UUID, actor: _Actor
) -> Project:
    """取项目行（先守卫 ⇒ ⇒ 无权 ⇒ 404）。"""
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=project_id,
        actor_roles=list(actor.roles),
    )
    project = await db.get(Project, project_id)
    if project is None:
        raise PcsError(
            code="PROJECT_NOT_FOUND",
            status=404,
            message=f"Project not found: {project_id}",
        )
    return project


@router.get("/{project_id}/bedd", response_model=BeddResponse)
async def get_bedd(
    project_id: uuid.UUID,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> BeddResponse:
    """读项目的 BEDD 文档（**没有 ⇒ 空文档**，不是 404）。"""
    require_roles(actor, *_READ_ROLES)
    project = await _get_project(db, project_id, actor)
    # ⚠️ **库里可能是旧形状 / 空** ⇒ ⇒ 校验不过就当空文档（不 500）
    try:
        document = BeddDocument.model_validate(project.bedd_json or {})
    except ValidationError:
        document = BeddDocument()
    return BeddResponse(
        project_id=str(project.project_id),
        document=document,
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
    )


@router.put("/{project_id}/bedd", response_model=BeddResponse)
async def put_bedd(
    project_id: uuid.UUID,
    payload: BeddDocument,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> BeddResponse:
    """整份写入 BEDD 文档（**未知分组 / 未知字段 ⇒ 422**）。"""
    require_roles(actor, *_WRITE_ROLES)
    project = await _get_project(db, project_id, actor)
    # ⚠️ **落库时丢掉 None** ⇒ ⇒ 库里是一份「填了哪些就是哪些」的稀疏文档
    project.bedd_json = payload.model_dump(exclude_none=True)
    await db.commit()
    await db.refresh(project)
    return BeddResponse(
        project_id=str(project.project_id),
        document=payload,
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
    )
