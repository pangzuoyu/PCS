"""待办**实时计算**（ADR-0049 §② / SPEC P9A-NOT-002）。

**不建 `todos` 表。** 待办的真值是「**当前**谁被卡住」，它由签署矩阵的当前
步骤决定，随每次签署推进自动改变。建表意味着每次推进都要 UPDATE 全部下游
步骤的 todo 行 —— 写放大，且引入了「todo 表与 matrix 表不一致」的窗口。

⇒ 没有一行会过期，因为每次查询都从真值重算。

## 「当前步骤」由观测行决定，不由客户端自述

与 `DeliverableService._assert_step_order` 同一判据：已完成/已跳过的
`step_order` 之外，最小的那个待签步骤就是当前的。**必须**复用同一判据 ——
两条规则漂移的症状很安静：签署端点说「该你签了」，待办列表说「没你什么事」。

## 角色判定：**全局角色**（不是项目内角色）

签署矩阵的 `sign_role` 与 **token 的 role claim** 比较（`sign_step` 里
`sign_role != actor_role` 就 403），项目那侧只校验**成员身份**。
⇒ 「能签第 N 步」= 有项目授权 **且** 全局角色 == step.sign_role。

待办若按 `role_in_project` 圈人，会列出那些**点了必然 403** 的待办 ——
「待办里有，点进去说你不是」比没有待办更坏。

## 项目范围只认 `user_projects`

`user_projects` 是 BLOCKER-3 之后**唯一**的 ACL 事实来源。刻意**不**把
`projects.created_by` 当兜底 —— 那会造出第二个授权来源，而两个来源漂移时
越权读不出来、也报不了错。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import Deliverable, DeliverableVersion, SignatureMatrix
from app.models.enums import (
    DeliverableSignStatus,
    WorkflowProgressState,
    WorkflowType,
)
from app.models.project import UserProject
from app.models.workflow_progress import WorkflowProgress


@dataclass(frozen=True)
class TodoItem:
    """一条待办。**每次查询现算**，不落库。"""

    deliverable_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID
    step_order: int
    step_role: str
    title: str


def current_step(
    steps: list[dict[str, Any]], done_orders: set[int]
) -> dict[str, Any] | None:
    """当前该签的步骤；全部步骤已终态时返回 None。"""
    for candidate in steps:
        if int(candidate.get("step_order", 0)) not in done_orders:
            return candidate
    return None


async def _my_project_ids(db: AsyncSession, *, actor_user_id: uuid.UUID) -> set[uuid.UUID]:
    """当前用户有权的项目（走 `user_projects`）。

    ADR-0049 §③：500ms 达标的前提是这一步有可用索引 ——
    `ix_user_projects_active (user_id, project_id, revoked_at)` 覆盖这个查询。
    """
    rows = await db.execute(
        select(UserProject.project_id).where(
            UserProject.user_id == actor_user_id, UserProject.revoked_at.is_(None)
        )
    )
    return {pid for (pid,) in rows.all()}


async def compute_todos(
    db: AsyncSession, *, actor_user_id: uuid.UUID, global_role: str
) -> list[TodoItem]:
    """算出「当前用户在这些项目上该签什么」。

    角色只用**全局角色**（token 的 role claim）—— 与 `sign_step` 实际校验的
    口径一致。

    ⚠️ **不用 `user_projects.role_in_project`**：`sign_step` 拿
    `actor.role`（token 的 role claim）与 `step["sign_role"]` 直接比较，
    不匹配就 403 `SIGN_STEP_ROLE_MISMATCH`；项目那侧（`_authorize` →
    `check_project_access_or_404`）只校验**成员身份**、不看角色。

    ⇒ 「能签第 N 步」= 有项目授权 **且** 全局角色 == step.sign_role。
    按项目内角色圈人，会列出那些**点了必然 403** 的待办 ——
    「待办里有，点进去说你不是」比没有待办更坏。
    """
    roles = {global_role}

    project_ids = await _my_project_ids(db, actor_user_id=actor_user_id)
    if not project_ids:
        return []

    deliverables = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.project_id.in_(project_ids),
                # 只覆盖 PENDING —— APPROVED / DRAFT 都没有待签步骤。
                Deliverable.sign_status == DeliverableSignStatus.PENDING,
            )
        )
    ).scalars().all()
    if not deliverables:
        return []

    by_id = {d.deliverable_id: d for d in deliverables}
    matrices = {
        m.matrix_id: m
        for m in (
            await db.execute(
                select(SignatureMatrix).where(
                    SignatureMatrix.matrix_id.in_({d.matrix_id for d in deliverables})
                )
            )
        ).scalars().all()
    }
    versions = (
        await db.execute(
            select(DeliverableVersion).where(
                DeliverableVersion.deliverable_id.in_(list(by_id))
            )
        )
    ).scalars().all()
    if not versions:
        return []

    done_by_version: dict[uuid.UUID, set[int]] = {}
    progress_rows = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == WorkflowType.SIGN,
                WorkflowProgress.workflow_id.in_({v.version_id for v in versions}),
            )
        )
    ).scalars().all()
    for r in progress_rows:
        if r.step_status in (
            WorkflowProgressState.COMPLETED,
            WorkflowProgressState.SKIPPED,
        ):
            done_by_version.setdefault(r.workflow_id, set()).add(r.step_order)

    out: list[TodoItem] = []
    for version in versions:
        deliverable = by_id[version.deliverable_id]
        matrix = matrices.get(deliverable.matrix_id)
        if matrix is None or not matrix.steps_json:
            continue
        steps = sorted(
            (s for s in matrix.steps_json if isinstance(s, dict)),
            key=lambda s: s.get("step_order", 0),
        )
        step = current_step(steps, done_by_version.get(version.version_id, set()))
        if step is None:
            continue
        role = str(step.get("sign_role", ""))
        if role not in roles:
            continue
        out.append(
            TodoItem(
                deliverable_id=deliverable.deliverable_id,
                version_id=version.version_id,
                project_id=deliverable.project_id,
                step_order=int(step.get("step_order", 0)),
                step_role=role,
                title=deliverable.title,
            )
        )
    out.sort(key=lambda t: (t.project_id, t.deliverable_id))
    return out


__all__ = ["TodoItem", "compute_todos", "current_step"]
