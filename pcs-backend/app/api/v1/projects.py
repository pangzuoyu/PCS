"""项目 API —— product_category 口径判据 + **项目创建**（P9B-2 · T-1）。

用户裁决 2026-10-05「按 project 产品类型强制」落地配套。

**背景**: PCS 长期没有 Project create API (`user_projects.py` 只做访问授权/查询,
`workspaces.py` 只管 workspace), product_category 只能在 DB/seed 层设置, 真实
项目运维成本高、且容易漏标 → 炼油项目静默按非炼油口径算能耗。

⚠️ **T-1（P9B-2 · 2026-10-27 用户裁决）补上 `POST /projects`** —— 没有它,
项目建不出来 ⇒ 签署流程的对象（记录 / 交付物）全都挂在项目下 ⇒ P9B-2 交付后
签署流程在**真实 UI** 上走不通（只能靠 mock 验证）。

**范围**: product_category 的可查可设 + **建项目**; **删除 / 列表**仍不做。

ACL: GET 需对该 project 有访问权 (或 SYSTEM_ADMIN);
     PATCH 限 SYSTEM_ADMIN —— 产品类别直接决定能耗折标口径, 不是普通编辑;
     POST 限 SYSTEM_ADMIN —— 建项目是**管理动作**（与 PATCH 同口径）。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.project import Project, Workspace
from app.models.util import UtilityEnergySummary
from app.schemas.project import ProductCategoryUpdate, ProjectCreate, ProjectOut
from app.services.exceptions import WorkspaceNotFoundError
from app.services.signature_matrix_service import SignatureMatrixService
from app.services.util.utility_energy_summary_service import (
    derive_electricity_value_type,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _is_project_no_unique_violation(exc: IntegrityError) -> bool:
    """这条 `IntegrityError` 是不是 `project_no` 的**唯一约束**冲突？（TODO-102）

    ⚠️ **只**对 `project_no` 唯一约束说 True —— 别的约束违约（NOT NULL /
    FK / CHECK）必须让调用方重新抛出（⇒ 500 + 服务端留详情），
    否则用户会被「项目编号已存在」这条**假提示**引到错误的方向
    （照提示换编号，换了还是错）。

    ## 两条判据（跨方言）

    1. **PG**：`exc.orig.diag.constraint_name` = `uq_projects_project_no`
       （本仓 `NAMING_CONVENTION` 的 `uq_%(table_name)s_%(column_0_name)s`）
       ⇒ 精确匹配约束名。
    2. **SQLite**：没有 `diag` ⇒ 消息形如
       `UNIQUE constraint failed: projects.project_no`
       ⇒ 匹配 `UNIQUE` + `project_no`。

    ⚠️ 两边都**必须**判「唯一」这一层 —— 只判「消息里有没有 project_no」
    会把 `projects.project_name` 的 NOT NULL 违约也算进去（子串）⇒
    又变回「另一种错说成编号重复」。
    """
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    if constraint_name:
        # PG：约束名精确匹配（本仓命名约定 ⇒ uq_projects_project_no）
        return constraint_name == "uq_projects_project_no"
    # SQLite（及任何没有 diag 的方言）：消息里必须**同时**有 UNIQUE 与 project_no
    text = str(orig if orig is not None else exc)
    return "UNIQUE" in text.upper() and "project_no" in text


def _to_out(record: Project) -> ProjectOut:
    return ProjectOut(
        project_id=record.project_id,
        project_no=record.project_no,
        project_name=record.project_name,
        project_type=record.project_type,
        product_category=record.product_category,
        electricity_value_type=derive_electricity_value_type(
            record.product_category
        ),
    )


@router.post(
    "",
    response_model=ProjectOut,
    status_code=http_status.HTTP_201_CREATED,
    summary="建项目（P9B-2 · T-1 · SYSTEM_ADMIN）",
)
async def create_project(
    payload: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> ProjectOut:
    """建项目，**同一事务**里默认绑一份 ACTIVE 的 RECORD 签署矩阵。

    ## 为什么必须「建项目」与「默认绑矩阵」同批

    R-17 之后**送审批准链由项目绑定的 `module='RECORD'` 矩阵推导** ⇒
    没绑矩阵的项目**送不了审**（后端 422 `RECORD_APPROVAL_MATRIX_NOT_BOUND`）
    ⇒ 新项目建出来就送不了审 ⇒ 用户看到的是 422 而不是引导。
    ⇒ **同批**落地 ⇒ 新项目**当场就能送审**。

    ## 事务边界

    建行 + 绑矩阵 + 建默认矩阵模板在**同一事务**里 ⇒ 任一步失败**全回滚**
    ⇒ 不会留下「项目建好了但送不了审」的半成品。
    """
    require_roles(user, "SYSTEM_ADMIN")
    workspace = await db.get(Workspace, payload.workspace_id)
    if workspace is None:
        # ⚠️ **不建孤儿项目**：`projects.workspace_id` 是 FK ⇒ 指向不存在的工作区
        # ⇒ 404（明确说「工作区没有」，而不是 500 的 FK 违约）。
        raise WorkspaceNotFoundError(f"工作区 {payload.workspace_id} 不存在")
    if workspace.workspace_type != "FORMAL":
        # ⚠️ **只收 FORMAL**（评审 #4）：下游每个签署动作都过
        #    `require_formal_project_workspace`（非 FORMAL ⇒ 403）⇒ 收下
        #    PERSONAL/TEMPORARY 的项目 = 建一个**永远送不了审**的半成品，
        #    却回 201 + 「已自动绑矩阵，可以提交批准了」的假承诺。
        raise PcsError(
            code="WORKSPACE_NOT_FORMAL",
            message=(
                f"工作区 {payload.workspace_id} 是 {workspace.workspace_type}，"
                "只有 FORMAL 工作区能建项目（个人/临时区无工程效力）"
            ),
            status=422,
        )
    record = Project(
        project_no=payload.project_no,
        project_name=payload.project_name,
        owner_company=payload.owner_company,
        location=payload.location,
        project_type=payload.project_type,
        design_phase=payload.design_phase,
        unit_system=payload.unit_system,
        workspace_id=payload.workspace_id,
        status=payload.status,
        product_category=payload.product_category.value,
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError as exc:
        # ⚠️ **只有** `project_no` 唯一约束冲突才是 409（TODO-102）；
        #    其它约束违约（NOT NULL / FK / CHECK）重新抛 ⇒ 500 + 服务端留详情，
        #    不把「另一种错」说成「编号重复」。
        #    —— 此前把**任何** IntegrityError 都报成 409 ⇒ 用户照提示换编号，
        #    换了还是错（真相是另一个约束违约）。
        if not _is_project_no_unique_violation(exc):
            raise
        # `project_no` 全局唯一（评审 #5）⇒ 重复编号是**可操作的冲突**，
        # 不是服务器坏了 —— 表单超时重提 / 手输已有编号都会走到这。
        await db.rollback()
        raise PcsError(
            code="PROJECT_NO_CONFLICT",
            message=f"项目编号 {payload.project_no} 已存在（全局唯一），请换一个",
            status=409,
        ) from exc
    await SignatureMatrixService.ensure_default_record_matrix(
        db, project_id=record.project_id
    )
    await db.commit()
    await db.refresh(record)
    return _to_out(record)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> ProjectOut:
    """读项目 + 当前生效的电折标口径 (product_category 的派生态, 便于核对)."""
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=list(user.roles),
    )
    record = (
        await db.execute(select(Project).where(Project.project_id == project_id))
    ).scalar_one_or_none()
    if record is None:
        # SYSTEM_ADMIN bypass 了访问权校验, 这里兜底 404 (不泄漏存在性)
        raise PcsError(
            code="PROJECT_NOT_FOUND", message=f"Project not found: {project_id}",
            status=404,
        )
    return _to_out(record)


@router.patch(
    "/{project_id}/product-category",
    response_model=ProjectOut,
    status_code=http_status.HTTP_200_OK,
)
async def set_product_category(
    project_id: uuid.UUID,
    payload: ProductCategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> ProjectOut:
    """设置项目产品类别 (SYSTEM_ADMIN) — 决定电折标用等价值还是当量值.

    **已有综合能耗汇总时拒绝 (422)**: 每条 UtilityEnergySummary 都固化了当时的
    `electricity_value_type`。改项目类别会让历史汇总与新口径不一致, 且无法追溯
    当时按哪个口径算的 → fail-closed, 要求先清理或另建项目。
    """
    require_roles(user, "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=list(user.roles),
    )
    record = (
        await db.execute(select(Project).where(Project.project_id == project_id))
    ).scalar_one_or_none()
    if record is None:
        raise PcsError(
            code="PROJECT_NOT_FOUND", message=f"Project not found: {project_id}",
            status=404,
        )

    existing = (
        await db.execute(
            select(func.count())
            .select_from(UtilityEnergySummary)
            .where(UtilityEnergySummary.project_id == project_id)
        )
    ).scalar_one()
    if existing:
        raise PcsError(
            code="PRODUCT_CATEGORY_LOCKED",
            message=(
                f"project {project_id} 已有 {existing} 条综合能耗汇总, "
                "product_category 已被固化在每条汇总的 electricity_value_type 中。"
                "改类别会让历史汇总口径不可追溯 → 请先清理该项目的汇总或另建项目。"
            ),
            status=422,
        )

    record.product_category = payload.product_category.value
    await db.commit()
    await db.refresh(record)
    return _to_out(record)
