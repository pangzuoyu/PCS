"""workflow_progress 读面（P9A B5 / SPEC P9A-OBS-003）。

写入面在 `app/services/workflow_progress_writer.py`（ADR-0047 §① 的唯一入口）；
本模块**只读**。读写分开是因为写有 ADR 级的硬约束（必须在 service 层、
与业务同事务），读没有 —— 把它们放一起会让「谁能写」的答案变模糊。

## 404 与空列表必须可分辨

`workflow_id` 是多态的，本模块要回答「这个工作流存不存在」就得按
`WorkflowType` 反查它的宿主行（版本 / 交付物）。查不到 ⇒ 404
`WORKFLOW_NOT_FOUND`；查得到但一条观测行都没有 ⇒ 200 + 空 `items`。

**不能**把后者也返成空数组：甘特图会把「你查错了 ID」画成「这条流程
一个节点都没有」，两者在界面上长得一模一样。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.deliverable import Deliverable, DeliverableVersion
from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress


def parse_workflow_type(value: str) -> WorkflowType:
    """URL 段 → `WorkflowType`。不认识 ⇒ 422 `WORKFLOW_TYPE_UNKNOWN`。

    422 而不是 404：「类型不认识」是请求形状错，「工作流不存在」是资源不存在。
    混成一个码，前端没法据此决定「改代码」还是「改数据」。
    """
    try:
        return WorkflowType(value)
    except ValueError as e:
        raise PcsError(
            code="WORKFLOW_TYPE_UNKNOWN",
            message=(
                f"未知工作流类型 {value!r}；"
                f"可用值：{[t.value for t in WorkflowType]}"
            ),
            status=422,
        ) from e


class WorkflowProgressService:
    """观测层读面。"""

    @staticmethod
    async def _resolve(
        db: AsyncSession, *, workflow_type: WorkflowType, workflow_id: uuid.UUID
    ) -> uuid.UUID:
        """反查工作流的宿主行，返回它所属的 `project_id`；查不到 ⇒ 404。

        ADR-0047 §① 的三类工作流各自对应不同的宿主：
        SIGN → `deliverable_versions`；另两类 → `deliverables`。
        """
        project_id: uuid.UUID | None = None
        if workflow_type is WorkflowType.SIGN:
            version = await db.get(DeliverableVersion, workflow_id)
            if version is None:
                project_id = None
            else:
                deliverable = await db.get(Deliverable, version.deliverable_id)
                project_id = deliverable.project_id if deliverable is not None else None
        else:
            deliverable = await db.get(Deliverable, workflow_id)
            project_id = deliverable.project_id if deliverable is not None else None

        if project_id is None:
            raise PcsError(
                code="WORKFLOW_NOT_FOUND",
                message=f"{workflow_type.value} 工作流 {workflow_id} 不存在",
                status=404,
            )
        return project_id

    @classmethod
    async def get(
        cls,
        db: AsyncSession,
        *,
        workflow_type: WorkflowType,
        workflow_id: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """取一条工作流的观测行 + 5 态计数。

        Args:
            project_id: 调用方已鉴权通过的项目 ID。传入后会**再查一次**
                `workflow_progress.project_id` 并要求一致 —— 授权依据是观测表
                那一列（`workflow_id` 多态，join 不回项目）。

        Returns:
            计数 dict（5 态全在）+ `items`（按 `step_order` 升序）。
        """
        resolved_project = await cls._resolve(
            db, workflow_type=workflow_type, workflow_id=workflow_id
        )
        if project_id is not None and resolved_project != project_id:
            raise PcsError(
                code="WORKFLOW_NOT_FOUND",
                message=f"{workflow_type.value} 工作流 {workflow_id} 不存在",
                status=404,
            )

        rows = (
            await db.execute(
                select(WorkflowProgress)
                .where(
                    WorkflowProgress.workflow_type == workflow_type,
                    WorkflowProgress.workflow_id == workflow_id,
                )
                .order_by(WorkflowProgress.step_order, WorkflowProgress.progress_id)
            )
        ).scalars().all()

        counts = {state: 0 for state in WorkflowProgressState}
        for row in rows:
            counts[row.step_status] = counts.get(row.step_status, 0) + 1

        return {
            "workflow_type": workflow_type,
            "workflow_id": workflow_id,
            "project_id": resolved_project,
            "total": len(rows),
            "counts": counts,
            "items": list(rows),
        }
