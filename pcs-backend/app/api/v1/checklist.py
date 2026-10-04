"""Checklist API（Sprint 1）。

P7-7+ BLOCKER-3 集成 (commit 23342 修订):
- 4 endpoint 全部用 Depends(current_actor) 替代裸 user_id query param
  (修复 IDOR 漏洞: 之前 user_id 由 query 注入, 客户端可伪造)
- project 级操作 (list_for_project/bulk_seed/completeness) 加
  check_project_access_or_404 守卫 (基于 actor.user_id)
- record 级操作 (update_item) 加 check_record_access_or_404 守卫
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404, check_record_access_or_404
from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.schemas.checklist import (
    ChecklistBulkSeed,
    ChecklistCompleteness,
    ChecklistItemOut,
    ChecklistItemPut,
)
from app.services.checklist_service import ChecklistService

router = APIRouter(prefix="/checklist", tags=["checklist"])


@router.get("/projects/{project_id}", response_model=list[ChecklistItemOut])
async def list_for_project(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChecklistItemOut]:
    """GET 列出项目输入清单（DICT V3.1 表 44）。

    步骤：
    1. BLOCKER-3 守卫: actor 必须有 project 访问权
    2. 转发 ChecklistService.list_for_project → 按 project_id 取行
       （按 item_key 升序，不分页）
    3. ORM 行 → ChecklistItemOut 序列化（FastAPI response_model 控制）

    ACL：DESIGNER / CHECKER / REVIEWER / APPROVER / SYSTEM_ADMIN
    BLOCKER-3 P7-7+ 集成：Depends(current_actor) + check_project_access_or_404
    （user_id 不可再由 query 注入，避免 IDOR 漏洞）
    """
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=user.roles,
    )
    svc = ChecklistService(session=db)
    rows = await svc.list_for_project(project_id)
    return [ChecklistItemOut.model_validate(r) for r in rows]


@router.post(
    "/projects/{project_id}/seed",
    response_model=list[ChecklistItemOut],
    status_code=201,
)
async def bulk_seed(
    project_id: uuid.UUID,
    payload: ChecklistBulkSeed,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChecklistItemOut]:
    """POST 批量种子（项目内 checklist 一次生成）。

    步骤：
    1. BLOCKER-3 守卫: actor 必须有 project 访问权
    2. 调 ChecklistService.bulk_seed：按 items 列表逐条创建 ChecklistItem
       （status 默认 NOT_STARTED；actor.user_id 记录创建者）
    3. session.commit() 落库（service 已 flush）
    4. ORM 行经 ChecklistItemOut.model_validate 转响应 schema 列表

    BLOCKER-3 P7-7+ 集成：actor.user_id 取代 query param user_id
    （修复 IDOR：user_id 不再可由客户端伪造）。
    """
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=user.roles,
    )
    svc = ChecklistService(session=db)
    rows = await svc.bulk_seed(
        project_id=project_id, items=payload.items, user_id=user.user_id,
    )
    await db.commit()
    return [ChecklistItemOut.model_validate(r) for r in rows]


@router.get(
    "/projects/{project_id}/completeness",
    response_model=ChecklistCompleteness,
)
async def completeness(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChecklistCompleteness:
    """GET 项目输入清单完成度统计。

    步骤：
    1. BLOCKER-3 守卫: actor 必须有 project 访问权
    2. 转发 ChecklistService.completeness → 按 project_id 取行
       → 派生 total / required_total / 3 桶分桶 / 百分比
    3. 返回 ChecklistCompleteness Pydantic 模型

    BLOCKER-3 P7-7+ 集成：Depends(current_actor) + check_project_access_or_404
    """
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=user.roles,
    )
    svc = ChecklistService(session=db)
    return await svc.completeness(project_id)


@router.put("/items/{checklist_id}", response_model=ChecklistItemOut)
async def update_item(
    checklist_id: uuid.UUID,
    payload: ChecklistItemPut,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChecklistItemOut:
    """PUT 校验一项状态（5 态流转 + Audit 落库）。

    步骤：
    1. BLOCKER-3 守卫: actor 必须有 record.project_id 访问权
       (先 fetch ChecklistItem 拿 project_id, 再 check_record_access_or_404)
    2. 调 ChecklistService.update_status（状态校验 + Audit + flush）
    3. service 抛 ValueError → 404（找不到 checklist 项；保留原 ValueError 契约）
    4. session.commit() 落库
    5. ORM 行经 ChecklistItemOut.model_validate 转响应 schema

    ACL：DESIGNER / CHECKER / REVIEWER / APPROVER / SYSTEM_ADMIN
    BLOCKER-3 P7-7+ 集成：Depends(current_actor) + check_record_access_or_404
    """
    from sqlalchemy import select as _sa_select
    from app.models.system import ProjectInputChecklist

    pre = (await db.execute(
        _sa_select(ProjectInputChecklist).where(
            ProjectInputChecklist.checklist_id == checklist_id
        )
    )).scalar_one_or_none()
    if pre is None:
        raise HTTPException(status_code=404, detail="ChecklistItem not found")
    await check_record_access_or_404(
        db, user_id=user.user_id, record=pre, actor_roles=user.roles,
    )
    svc = ChecklistService(session=db)
    try:
        row = await svc.update_status(
            checklist_id=checklist_id, payload=payload, user_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await db.commit()
    return ChecklistItemOut.model_validate(row)