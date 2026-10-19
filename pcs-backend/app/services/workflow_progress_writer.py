"""workflow_progress 的**唯一**写入口（ADR-0047 §① 🔒 / P9A-OBS-002）。

## 为什么是「唯一」

ADR-0047 §① 把写入层定在 service 层，理由是实测的可达路径：
`StateMachineService.transition()` 有 4 条入口，其中 `cia_engine.py:85`
（`cia_mark_stale` 事件处理者）由 `app/workers/cia_tasks.py` 的 ARQ cron 驱动，
**完全不经过 API 层**。写入若写在 `app/api/v1/*` 的路由处理函数里，
所有 cron 驱动的状态变更在观测层里**系统性隐形，且不报错、不告警** ——
甘特图看起来是通的，只是漏掉了最该被观测的那部分。

推论（本模块存在的理由）：**观测写入的可测试性跟着 service 走**。
service 能被单测直接调用而绕过 HTTP；若写入在 API 层，
「service 单测全绿」会掩盖「观测层在生产的主要路径上根本没被触发」。

`test_writer_has_no_second_entry_point` 钉住这个唯一性 —— 多一个入口就多一条
能绕开 ADR 的路，而绕开的那条路不会有人记得回来补观测。

## 事务语义（ADR-0047 §②③）

同步写、与业务状态同一事务。**本模块不 commit** —— 由调用方负责，
这样观测写失败会连同业务变更一起回滚（观测层不可信的代价远高于
「多一次 INSERT 拖慢几毫秒」）。`test_does_not_commit` 钉住这条。

## 写入策略：按 (workflow_type, workflow_id, step_order) upsert

同一工作流的同一步骤只有一行。重复签署**更新**而非追加 ——
追加会让甘特图出现两个同序号步骤，而读 API 分不出哪条是当前的。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress

#: 终态集合 —— 这三种之后该步骤不再推进，故都要打 completed_at。
#: FAILED 在内：失败恰恰是最该被看见的一步，少给它打时间戳，
#: 甘特图上它会永远显示「进行中」，超时告警对它不触发。
_TERMINAL_STATES = frozenset(
    {
        WorkflowProgressState.COMPLETED,
        WorkflowProgressState.SKIPPED,
        WorkflowProgressState.FAILED,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


async def record_step(
    *,
    session: AsyncSession,
    project_id: uuid.UUID,
    workflow_type: WorkflowType,
    workflow_id: uuid.UUID,
    step_order: int,
    step_role: str,
    state: WorkflowProgressState,
    actor_user_id: uuid.UUID | None,
    result_hash: str | None = None,
) -> WorkflowProgress:
    """写一行工作流节点进度（同键则更新）。**不 commit。**

    Args:
        project_id: 所属项目。`workflow_id` 是多态的（版本 ID / 交付物 ID），
            无法 join 回项目，读 API 的项目鉴权（B5）只能靠这一列。
        workflow_type: ADR-0047 §① 的 3 类工作流之一。
        step_order: 步骤序号（与 `SignatureMatrix.steps_json.step_order` 同义）。
        step_role: 步骤角色（`steps_json.sign_role`）。
        state: 5 态之一。
        actor_user_id: 本步办理人，写入 `assignee`。
        result_hash: 步骤产物的哈希（签署快照 / 审批结论），可空。

    Returns:
        新建或更新后的 `WorkflowProgress` 行。
    """
    existing = (
        await session.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == workflow_type,
                WorkflowProgress.workflow_id == workflow_id,
                WorkflowProgress.step_order == step_order,
            )
        )
    ).scalar_one_or_none()

    now = _now()
    if existing is None:
        row = WorkflowProgress(
            project_id=project_id,
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            step_order=step_order,
            step_role=step_role,
            step_status=state,
            # started_at 在「首次进入该步骤」时打：IN_PROGRESS 才打，
            # 而一旦打过就不再覆盖（重签同一步不能把开始时间往前挪，
            # 否则甘特图上这一步的耗时会越改越短）。
            started_at=now if state == WorkflowProgressState.IN_PROGRESS else None,
            completed_at=now if state in _TERMINAL_STATES else None,
            assignee=actor_user_id,
            result_hash=result_hash,
            created_by=actor_user_id,
        )
        session.add(row)
        return row

    existing.project_id = project_id
    existing.step_role = step_role
    existing.step_status = state
    existing.assignee = actor_user_id
    if result_hash is not None:
        existing.result_hash = result_hash
    if state == WorkflowProgressState.IN_PROGRESS and existing.started_at is None:
        existing.started_at = now
    existing.completed_at = now if state in _TERMINAL_STATES else None
    return existing
