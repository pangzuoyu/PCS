"""项目模板 API（P10-K · W-3 / W-3d · SPEC §7.5 项目向导第 3 步）。

## 为什么**独立文件**（而不是塞进 `projects.py`）

`project_templates` 是**配置层**实体（公司级模板）⇒ ⇒ ⇒ 它的读面
（列模板）**不属于**项目的读写面 ⇒ ⇒ ⇒ 分开 ⇒ ⇒ ⇒ 一个文件一件事。

⚠️ **但「应用模板」端点的路径在项目下**（`/projects/{id}/apply-template`）
⇒ ⇒ ⇒ 所以本 router **不设 prefix** ⇒ ⇒ ⇒ 路径逐字写在装饰器上。

## ACL

| 端点 | 闸 |
|---|---|
| `GET /project-templates` | **SYSTEM_ADMIN only**（模板是**管理面**的对象）|
| `POST /projects/{id}/apply-template` | **SYSTEM_ADMIN** + **项目守卫**（要对该项目有权）|

## ⚠️ **为什么列表响应是**命名模型**

`scripts/check_openapi_payload_coverage.py` 的棘轮 = 「裸字段数 ≤ 基线」
⇒ ⇒ ⇒ 而基线**恰好顶满**（71）⇒ ⇒ ⇒ ⇒ 任何新增的**裸 object** 端点
⇒ ⇒ ⇒ **立刻爆** ⇒ ⇒ ⇒ 所以 `ProjectTemplateSummary` 是**必填**的
⇒ ⇒ ⇒（⚠️ **不要照抄** `pipe_codes.py:131` 那个**没有 `response_model`**
的端点 —— 它是最容易抄到的形状 ⇒ ⇒ ⇒ 抄它就把棘轮推爆）。

⇒ ⇒ ⇒ 且响应**不含 `default_config_json`**（完整 7 段配置）⇒ ⇒ ⇒
列表只给「够选择的信息」⇒ ⇒ ⇒ 完整配置在**应用**时才读。
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.enums import AuditAction
from app.schemas.project_template import ApplyTemplateRequest, ProjectTemplateSummary
from app.services.audit_service import AuditService
from app.services.project_template_service import ProjectTemplateService

router = APIRouter(tags=["project-templates"])


@router.get(
    "/project-templates",
    response_model=list[ProjectTemplateSummary],
    summary="列已发布的项目模板（SYSTEM_ADMIN · P10-K · W-3）",
)
async def list_project_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> list[ProjectTemplateSummary]:
    """列**已发布**（`status='PUBLISHED'`）的项目模板。

    ⚠️ **只列 PUBLISHED** —— 模板**没有发布端点**（本批只有 seed 写
    PUBLISHED · 运营流程另开 · TODO-206）⇒ ⇒ ⇒ ⇒ 列 DRAFT/OBSOLETE
    ⇒ ⇒ ⇒ 会让用户选到**没人审核过**的模板。
    """
    require_roles(user, "SYSTEM_ADMIN")
    return await ProjectTemplateService.list_published(db)


@router.post(
    "/projects/{project_id}/apply-template",
    response_model=dict,
    status_code=http_status.HTTP_200_OK,
    summary="把模板应用到项目（SYSTEM_ADMIN · P10-K · W-3d）",
)
async def apply_template(
    project_id: uuid.UUID,
    payload: ApplyTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> dict:
    """把模板应用到项目（**同一事务** · **幂等**）。

    ⚠️ **7 段任一段失败 ⇒ ⇒ ⇒ 全部回滚** ⇒ ⇒ ⇒ 项目不会被配成
    「一半模板、一半默认」⇒ ⇒ ⇒ ⇒ 所以端点**只 commit 一次**
    （在服务层返回之后）⇒ ⇒ ⇒ 任一段抛错 ⇒ ⇒ ⇒ 事务回滚 ⇒ ⇒ ⇒ 零残留。

    ⚠️ **`record_approval` 只替「自动绑的默认」** ⇒ ⇒ ⇒ 人工改过的
    签署矩阵绑定**不被夺走**（见 `ProjectTemplateService.apply_to_project`）。

    ⚠️ **写一条审计**（W-17）—— 模板应用 = **改变「谁该签」**的治理动作
    ⇒ ⇒ ⇒ 而 `signature_matrix_service` 里**零审计** ⇒ ⇒ ⇒ 这一条
    **由本端点补上**。
    """
    require_roles(user, "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=list(user.roles),
    )
    result = await ProjectTemplateService.apply_to_project(
        db,
        project_id=project_id,
        template_id=payload.template_id,
        actor=user,
        # ⚠️ **「单位制由谁决定」由调用方说**（D1 裁决）⇒ ⇒ ⇒ 后端**不猜**
        # ⇒ ⇒ ⇒ 「用户动没动过」只有向导知道（它持有表单状态）。
        unit_system_source=payload.unit_system_source.value,
    )
    await db.commit()
    await AuditService(db).write(
        action=AuditAction.PROJECT_TEMPLATE_APPLIED,
        resource_type="project",
        resource_id=str(project_id),
        user_id=user.user_id,
        detail={
            "template_id": result["template_id"],
            "template_name": result["template_name"],
            "template_version": result["template_version"],
            "segments": result["segments"],
        },
    )
    await db.commit()
    return result
