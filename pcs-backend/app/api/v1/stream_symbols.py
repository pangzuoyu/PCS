"""物流符号表端点（SYM-3 / SUP-002 §8）。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.services.stream_symbol_service import StreamSymbolService

router = APIRouter(tags=["stream-symbols"])


class CreateSymbolRequest(BaseModel):
    symbol: str
    name: str
    category: str | None = None
    version: str | None = "1"


class UpdateSymbolRequest(BaseModel):
    name: str | None = None
    category: str | None = None


class ProjectSymbolRequest(BaseModel):
    symbol: str
    name: str
    category: str | None = None


class ProjectSymbolUpdateRequest(BaseModel):
    override: dict = {}
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None


class ForkProjectSymbolRequest(BaseModel):
    symbol_id: UUID | None = None


# ---------- 公司级 ----------
@router.get("/stream-symbols")
async def list_company_symbols(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.list_company(db)


@router.post("/stream-symbols", status_code=201)
async def create_company_symbol(
    payload: CreateSymbolRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.create_company(
        db, data=payload.model_dump(), actor=user,
    )


@router.get("/stream-symbols/{symbol_id}")
async def get_company_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.get(db, symbol_id)


@router.put("/stream-symbols/{symbol_id}")
async def update_company_symbol(
    symbol_id: UUID,
    payload: UpdateSymbolRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.update_company(
        db, symbol_id, data=payload.model_dump(exclude_none=True), actor=user,
    )


@router.delete("/stream-symbols/{symbol_id}", status_code=204)
async def delete_company_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await StreamSymbolService.delete_company(db, symbol_id, actor=user)


@router.post("/stream-symbols/{symbol_id}/submit")
async def submit_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.submit(db, symbol_id, actor=user)


@router.post("/stream-symbols/{symbol_id}/approve")
async def approve_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await StreamSymbolService.approve(db, symbol_id, actor=user)


@router.post("/stream-symbols/{symbol_id}/publish")
async def publish_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "APPROVER", "SYSTEM_ADMIN")
    return await StreamSymbolService.publish(db, symbol_id, actor=user)


@router.post("/stream-symbols/{symbol_id}/obsolete")
async def obsolete_symbol(
    symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "REVIEWER", "SYSTEM_ADMIN")
    return await StreamSymbolService.obsolete(db, symbol_id, actor=user)


# ---------- 项目级 ----------
@router.post("/projects/{project_id}/stream-symbols/fork", status_code=201)
async def fork_project_symbols(
    project_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ForkProjectSymbolRequest | None = None,
):
    """symbol_id 缺省 → 复制全部公司级符号；指定时只 fork 一个。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    symbol_id = payload.symbol_id if payload else None
    return await StreamSymbolService.fork_to_project(
        db,
        project_id=project_id,
        symbol_id=symbol_id,
        actor=user,
    )


@router.get("/projects/{project_id}/stream-symbols")
async def list_project_symbols(
    project_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_company: bool = True,
):
    """GET 列出项目作用域流股符号（可含公司级一并）。

    步骤：
    1. ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 转发到 StreamSymbolService.list_project
    3. include_company=True（默认）：合并公司级 StreamSymbol（fork 的源头）
       + 项目级 ProjectStreamSymbol（项目内派生）；False 时仅项目级

    与 /stream-symbols（公司级 list_company_symbols）区别：本端点按项目
    隔离，含公司级需 include_company=True。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.list_project(
        db, project_id=project_id, include_company=include_company,
    )


@router.post("/projects/{project_id}/stream-symbols", status_code=201)
async def add_project_symbol(
    project_id: UUID,
    payload: ProjectSymbolRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """POST 项目作用域新增流股符号（201 Created）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（项目符号工艺侧编辑权限）
    2. 转发到 StreamSymbolService.add_project_symbol（service 层负责
       (project_id, symbol) 复合唯一查重 + PROJECT_STREAM_SYMBOL_DUP 409）
    3. service 写入由 service 层 db.commit() 负责（已含事务结束）

    返回新创建的 ProjectStreamSymbol（service 直接返回 ORM 行，FastAPI
    自动经 response_model 序列化）。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.add_project_symbol(
        db,
        project_id=project_id,
        symbol=payload.symbol,
        name=payload.name,
        category=payload.category,
        actor=user,
    )


@router.put("/projects/{project_id}/stream-symbols/{project_symbol_id}")
async def update_project_symbol(
    project_id: UUID,
    project_symbol_id: UUID,
    payload: ProjectSymbolUpdateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """PUT 改项目作用域流股符号（增量覆盖）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（项目符号工艺侧编辑权限）
    2. payload.model_dump(exclude_none=True) 排除 None 字段，仅提交显式给出的
       override / name / category / is_active，避免无意清空
    3. 转发到 StreamSymbolService.update_project_symbol（service 层
       按字段名增量覆盖，不动 source 字段）
    4. service 提交（已 commit），返回更新行

    注意：本端点不提供 status 流放接口，项目符号无状态机；如需作废走
    delete_project_symbol 或 add_project_symbol 重新创建。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await StreamSymbolService.update_project_symbol(
        db,
        project_symbol_id=project_symbol_id,
        data=payload.model_dump(exclude_none=True),
        actor=user,
    )


@router.delete("/projects/{project_id}/stream-symbols/{project_symbol_id}", status_code=204)
async def delete_project_symbol(
    project_id: UUID,
    project_symbol_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """DELETE 项目作用域流股符号（204 No Content）。

    步骤：
    1. ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    2. 转发到 StreamSymbolService.delete_project_symbol
    3. service 层无引用检查（项目内派生数据无下游引用），直接删行 + commit
    4. 204 No Content（FastAPI status_code 控制响应体为空）

    与 delete_company_symbol 区别：项目级不做引用检查（项目内派生数据
    不会被其他项目引用）；公司级需检查 ProjectStreamSymbol.source_symbol_id
    反向引用（STREAM_SYMBOL_IN_USE 409）。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await StreamSymbolService.delete_project_symbol(
        db, project_symbol_id=project_symbol_id, actor=user,
    )