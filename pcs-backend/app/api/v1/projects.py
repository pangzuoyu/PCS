"""项目产品类别 API (product_category — GB 30251-2024 §6.1.5 电折标口径判据).

用户裁决 2026-10-05「按 project 产品类型强制」落地配套。

**背景**: PCS 长期没有 Project create API (`user_projects.py` 只做访问授权/查询,
`workspaces.py` 只管 workspace), product_category 只能在 DB/seed 层设置, 真实
项目运维成本高、且容易漏标 → 炼油项目静默按非炼油口径算能耗。

**范围**: 只做 product_category 的可查可设, **不做完整 Project CRUD**
(创建/删除/列表超出本次范围)。项目本体仍由外部导入/直改 DB 建立。

ACL: GET 需对该 project 有访问权 (或 SYSTEM_ADMIN);
     PATCH 限 SYSTEM_ADMIN —— 产品类别直接决定能耗折标口径, 不是普通编辑。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.project import Project
from app.models.util import UtilityEnergySummary
from app.schemas.project import ProductCategoryUpdate, ProjectOut
from app.services.util.utility_energy_summary_service import (
    derive_electricity_value_type,
)

router = APIRouter(prefix="/projects", tags=["projects"])


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
