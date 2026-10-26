"""签署矩阵管理端点（TODO-070 · P9A-DLV-011 T3）。

## 为什么现在才有这个面

`signature_matrices` 表**恒为 0 行**且全仓**没有任何地方创建矩阵**
（P9A-DLV-007 之前）⇒ 变更单（`deliverables.matrix_id` NOT NULL + FK）
**建不出来**。P9A-DLV-007 补了「惰性建**内置**模板」这一条最小路径，
但**项目自定义矩阵仍然建不了** ⇒ 交付物的签发路径同样受阻。

## 权限**分层**（用户 2026-10-26 裁决）

| 动作 | 谁能做 |
|---|---|
| 建/改矩阵**模板** | **SYSTEM_ADMIN**（模板是**全局表** ⇒ 一个项目能改它 ⇒
  别的项目在用的矩阵跟着变） |
| 绑定/解绑**项目** | 全局角色 ∈ {DESIGNER, PROCESS_CONTROLLER, SYSTEM_ADMIN} **且**有该项目授权 |

绑定决定「本项目谁该签这一步」⇒ 与「签发」同级（`deliverables._ISSUE_ROLES` 同形）。

⚠️ 项目内角色词表（`user_projects.role_in_project` = DESIGNER/CHECKER/APPROVER/
REVIEWER/VIEWER）**无序**（平行职责，不是等级）⇒ 不按它分级；按**全局角色**
判权限，与既有端点（`_ISSUE_ROLES`）口径一致。

## 读面不需要项目授权

矩阵模板是**全局配置**（不是项目数据）⇒ 读它只要登录 + 角色，
不需要项目授权 —— 否则「我要看看我项目用的矩阵长什么样」会被 404 挡住。
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import (
    check_project_access_or_404,
    require_active_project_member,
)
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.deliverable import SignatureMatrix
from app.schemas.signature_matrix import (
    MatrixBindingRequest,
    MatrixBindingResponse,
    MatrixStepResponse,
    MatrixUnbindResponse,
    SignatureMatrixListResponse,
    SignatureMatrixRequest,
    SignatureMatrixResponse,
    SignatureMatrixUpdateRequest,
)
from app.services.signature_matrix_service import SignatureMatrixService

router = APIRouter(tags=["signature-matrices"])

#: 读矩阵 = 能读交付物的角色（矩阵决定「谁该签」，看不到矩阵就没法解释流程）
_READ_ROLES = (
    "DESIGNER",
    "PROCESS_CONTROLLER",
    "REVIEWER",
    "APPROVER",
    "CHECKER",
    "SYSTEM_ADMIN",
)

#: 改矩阵**模板** = SYSTEM_ADMIN（全局表，见模块 docstring）
_ADMIN_ROLES = ("SYSTEM_ADMIN",)

#: 绑定/解绑项目 = 项目负责人侧（与 `_ISSUE_ROLES` 同形）
_BIND_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")


def _to_response(matrix: SignatureMatrix) -> SignatureMatrixResponse:
    return SignatureMatrixResponse(
        matrix_id=matrix.matrix_id,
        matrix_name=matrix.matrix_name,
        module=matrix.module,
        doc_type=matrix.doc_type,
        version_purpose=matrix.version_purpose,
        status=matrix.status,
        steps=[
            MatrixStepResponse(
                step_order=int(s.get("step_order", 0)),
                sign_role=str(s.get("sign_role", "")),
                required=bool(s.get("required", True)),
                can_self_check=bool(s.get("can_self_check", True)),
                can_skip=bool(s.get("can_skip", False)),
            )
            for s in (matrix.steps_json or [])
            if isinstance(s, dict)
        ],
        created_at=matrix.created_at,
        updated_at=matrix.updated_at,
    )


@router.get(
    "/signature-matrices",
    response_model=SignatureMatrixListResponse,
    summary="列签署矩阵模板",
)
async def list_signature_matrices(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    module: str | None = Query(None, description="按模块过滤"),
    status: str | None = Query(None, description="按状态过滤（DRAFT/PENDING/ACTIVE/OBSOLETE）"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> SignatureMatrixListResponse:
    """列矩阵模板（全局配置 ⇒ 不按项目过滤）。"""
    require_roles(actor, *_READ_ROLES)
    items, total = await SignatureMatrixService.list_matrices(
        db, module=module, status=status, limit=limit, offset=offset
    )
    return SignatureMatrixListResponse(
        items=[_to_response(m) for m in items], total=total
    )


@router.post(
    "/signature-matrices",
    response_model=SignatureMatrixResponse,
    summary="建签署矩阵模板（SYSTEM_ADMIN）",
)
async def create_signature_matrix(
    body: SignatureMatrixRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SignatureMatrixResponse:
    """建一个矩阵模板。

    ⚠️ **写入时严格校验**（`validate_steps`）：任一步不合法 ⇒ 422，
    **不部分入库**（否则「签署少一道校审」而没人知道）。
    """
    require_roles(actor, *_ADMIN_ROLES)
    matrix = await SignatureMatrixService.create_matrix(
        db,
        matrix_name=body.matrix_name,
        module=body.module,
        doc_type=body.doc_type,
        version_purpose=body.version_purpose,
        steps=[s.model_dump() for s in body.steps],
        status=body.status,
    )
    await db.commit()
    return _to_response(matrix)


@router.get(
    "/signature-matrices/{matrix_id}",
    response_model=SignatureMatrixResponse,
    summary="签署矩阵详情",
)
async def get_signature_matrix(
    matrix_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SignatureMatrixResponse:
    """取矩阵详情（不存在 ⇒ 404 `SIGNATURE_MATRIX_NOT_FOUND`）。"""
    require_roles(actor, *_READ_ROLES)
    matrix = await SignatureMatrixService.get_matrix(db, matrix_id=matrix_id)
    return _to_response(matrix)


@router.put(
    "/signature-matrices/{matrix_id}",
    response_model=SignatureMatrixResponse,
    summary="改签署矩阵模板（SYSTEM_ADMIN）",
)
async def update_signature_matrix(
    matrix_id: uuid.UUID,
    body: SignatureMatrixUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SignatureMatrixResponse:
    """改矩阵模板（部分更新；`steps` 给了就整体替换）。"""
    require_roles(actor, *_ADMIN_ROLES)
    matrix = await SignatureMatrixService.update_matrix(
        db,
        matrix_id=matrix_id,
        matrix_name=body.matrix_name,
        module=body.module,
        doc_type=body.doc_type,
        version_purpose=body.version_purpose,
        steps=(
            [s.model_dump() for s in body.steps] if body.steps is not None else None
        ),
        status=body.status,
    )
    await db.commit()
    # ⚠️ **必须 refresh**：`updated_at` 是 `onupdate=func.now()`（**服务端**表达式）
    # ⇒ UPDATE flush 之后该属性被标记 expired ⇒ 在 async 上下文里读它会触发
    # 懒加载 ⇒ `MissingGreenlet` ⇒ 全局兜底 ⇒ **500 INTERNAL_ERROR**。
    # （「没改字段的 PUT」不发 UPDATE ⇒ 反而是绿的 —— 改了必挂、没改假绿。）
    await db.refresh(matrix)
    return _to_response(matrix)


@router.post(
    "/projects/{project_id}/signature-matrices",
    response_model=MatrixBindingResponse,
    summary="把矩阵绑到项目（项目负责人侧）",
)
async def bind_project_matrix(
    project_id: uuid.UUID,
    body: MatrixBindingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> MatrixBindingResponse:
    """绑定矩阵到「项目 × 模块」（换绑 = 改同一行）。

    ⚠️ 同一项目同一模块**只可能有一行**绑定（唯一约束，迁移 `p9_008`）
    ⇒ 「谁该签这一步」不会有两个答案。
    """
    require_roles(actor, *_BIND_ROLES)
    await check_project_access_or_404(
        db, user_id=actor.user_id, project_id=project_id, actor_roles=actor.roles
    )
    # ⚠️ 授权 ≠ 有权做这件事：项目内 **VIEWER**（只读）也能通过上面的 404 门
    # ⇒ 但「决定本项目谁该签」不该给只读成员 ⇒ 再要一道「活跃参与者」门。
    await require_active_project_member(
        db, user_id=actor.user_id, project_id=project_id, actor_roles=actor.roles
    )
    binding = await SignatureMatrixService.bind_to_project(
        db, project_id=project_id, module=body.module, matrix_id=body.matrix_id
    )
    await db.commit()
    matrix = await SignatureMatrixService.get_matrix(db, matrix_id=binding.matrix_id)
    return MatrixBindingResponse(
        project_id=binding.project_id,
        module=binding.module,
        matrix_id=binding.matrix_id,
        matrix_name=matrix.matrix_name,
    )


@router.delete(
    "/projects/{project_id}/signature-matrices/{module}",
    response_model=MatrixUnbindResponse,
    summary="解绑项目的矩阵（项目负责人侧）",
)
async def unbind_project_matrix(
    project_id: uuid.UUID,
    module: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> MatrixUnbindResponse:
    """解绑（本来就没绑 ⇒ `unbound=false`，**不是** 404）。"""
    require_roles(actor, *_BIND_ROLES)
    await check_project_access_or_404(
        db, user_id=actor.user_id, project_id=project_id, actor_roles=actor.roles
    )
    await require_active_project_member(
        db, user_id=actor.user_id, project_id=project_id, actor_roles=actor.roles
    )
    unbound = await SignatureMatrixService.unbind_from_project(
        db, project_id=project_id, module=module
    )
    await db.commit()
    return MatrixUnbindResponse(project_id=project_id, module=module, unbound=unbound)
