"""workflow_progress_writer 测试（ADR-0047 观测层的**唯一写入口**）。

## 为什么这个文件的每条用例都在测「写进去没有」而不是「写了什么」

ADR-0047 §① 的核心风险是**观测层出现系统性盲区且不报错**：
写入若放在 API 层，ARQ cron 驱动的状态变更（`cia_mark_stale`）在观测层里
全部隐形 —— 甘特图看起来是通的，只是漏掉了最需要观测的那部分。
所以本文件直接调 service，**不经 HTTP**。

## 事务语义（同生共死）

ADR-0047 §②③：同步写、与业务状态同一事务。观测写失败 ⇒ 主状态变更回滚。
反过来也成立 —— 主流程回滚时观测行必须一起消失。`test_does_not_commit`
钉住「写入方不自己 commit」，否则观测行会比业务数据先落库，
排障时看到的是「流程没走但进度动了」。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress
from app.services.workflow_progress_writer import record_step

pytestmark = pytest.mark.asyncio


async def _rows(db):
    return (
        await db.execute(select(WorkflowProgress).order_by(WorkflowProgress.step_order))
    ).scalars().all()


async def test_record_step_inserts_a_row(db_session):
    await record_step(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        state=WorkflowProgressState.IN_PROGRESS,
        actor_user_id=uuid.uuid4(),
    )
    await db_session.commit()

    rows = await _rows(db_session)
    assert len(rows) == 1
    assert rows[0].step_order == 1
    assert rows[0].step_role == "DESIGNER"


async def test_record_step_upserts_rather_than_duplicating(db_session):
    """同一 (workflow_type, workflow_id, step_order) 只有一行。

    重复签署若追加第二行，甘特图会出现两个同序号步骤，
    而读 API 分不出哪条是当前的 —— 它们长得一模一样。
    """
    kwargs = dict(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        actor_user_id=uuid.uuid4(),
    )
    await record_step(
        **kwargs, state=WorkflowProgressState.IN_PROGRESS
    )
    await db_session.commit()
    await record_step(**kwargs, state=WorkflowProgressState.COMPLETED)
    await db_session.commit()

    rows = await _rows(db_session)
    assert len(rows) == 1
    assert rows[0].step_status == WorkflowProgressState.COMPLETED


async def test_record_step_sets_assignee_from_actor(db_session):
    """负责人取实际办理人 —— 甘特图的「责任人」列与超时告警都靠它。"""
    actor = uuid.uuid4()
    await record_step(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        state=WorkflowProgressState.IN_PROGRESS,
        actor_user_id=actor,
    )
    await db_session.commit()

    assert (await _rows(db_session))[0].assignee == actor


async def test_record_step_stamps_started_at_on_first_write(db_session):
    await record_step(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        state=WorkflowProgressState.IN_PROGRESS,
        actor_user_id=uuid.uuid4(),
    )
    await db_session.commit()

    row = (await _rows(db_session))[0]
    assert row.started_at is not None, "IN_PROGRESS 必须有 started_at（甘特图算时长）"
    assert row.completed_at is None, "未终态不该有 completed_at"


async def test_record_step_stamps_completed_at_on_terminal_state(db_session):
    """COMPLETED / FAILED / SKIPPED 都算终态 —— 三者都要 completed_at。

    少一个的后果：FAILED 的步骤在甘特图上永远「进行中」，超时告警对它不触发，
    而失败恰恰是最该被看见的那一步。
    """
    for i, state in enumerate(
        [
            WorkflowProgressState.COMPLETED,
            WorkflowProgressState.FAILED,
            WorkflowProgressState.SKIPPED,
        ],
        start=1,
    ):
        await record_step(
            session=db_session,
            project_id=uuid.uuid4(),
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=uuid.uuid4(),
            step_order=i,
            step_role="REVIEWER",
            state=state,
            actor_user_id=uuid.uuid4(),
        )
    await db_session.commit()

    rows = await _rows(db_session)
    assert len(rows) == 3
    assert all(r.completed_at is not None for r in rows), (
        f"有终态没打 completed_at：{[(r.step_order, r.step_status) for r in rows]}"
    )


async def test_record_step_does_not_commit(db_session):
    """写入方**不**自己 commit —— 观测与业务同生共死（ADR-0047 §③）。

    若 record_step 内部 commit，观测行会比业务数据先落库：
    主流程回滚了而进度显示「已完成」，排障时会被当成观测层不可信
    —— 而它本来是出问题时要信的东西。
    """
    await record_step(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        state=WorkflowProgressState.IN_PROGRESS,
        actor_user_id=uuid.uuid4(),
    )
    await db_session.rollback()

    assert await _rows(db_session) == []


async def test_record_step_records_result_hash_when_given(db_session):
    """result_hash 是步骤产物的溯源凭据（签署快照/审批结论）。"""
    await record_step(
        session=db_session,
        project_id=uuid.uuid4(),
        workflow_type=WorkflowType.SIGN,
        workflow_id=uuid.uuid4(),
        step_order=1,
        step_role="DESIGNER",
        state=WorkflowProgressState.COMPLETED,
        actor_user_id=uuid.uuid4(),
        result_hash="a" * 64,
    )
    await db_session.commit()

    assert (await _rows(db_session))[0].result_hash == "a" * 64


async def test_record_step_separates_workflows_by_type(db_session):
    """同一 workflow_id 在不同 workflow_type 下是两条独立进度。

    （理论上不该发生，但 UNIQUE 键含 workflow_type 正是为此 ——
      若哪天把 workflow_id 复用成项目 ID，读 API 会把三条工作流叠成一条。）
    """
    wf = uuid.uuid4()
    for wt in (WorkflowType.SIGN, WorkflowType.CHANGE_NOTICE):
        await record_step(
            session=db_session,
            project_id=uuid.uuid4(),
            workflow_type=wt,
            workflow_id=wf,
            step_order=1,
            step_role="DESIGNER",
            state=WorkflowProgressState.IN_PROGRESS,
            actor_user_id=uuid.uuid4(),
        )
    await db_session.commit()

    assert len(await _rows(db_session)) == 2


async def test_writer_has_no_second_entry_point(db_session):
    """观测写入**只能**经 record_step —— 模块不得暴露别的写函数。

    这不是风格约束：ADR-0047 §① 说「若某个流程的触发方本身已在 service 层，
    写入随该 service，不上移到任何 API 层」。多一个入口就多一条能绕开
    ADR 的路，而绕开的那条路不会有人记得回来补观测。
    """
    import app.services.workflow_progress_writer as mod

    public = [
        name
        for name in dir(mod)
        if not name.startswith("_") and callable(getattr(mod, name))
        and getattr(mod, name).__module__ == mod.__name__
    ]
    assert public == ["record_step"], f"观测写入出现第二个入口：{public}"


async def test_row_count_is_one_per_step(db_session):
    """一条粗粒度的守门：写 3 步就该有 3 行（防 upsert 写串了 workflow_id）。"""
    wf = uuid.uuid4()
    for order in (1, 2, 3):
        await record_step(
            session=db_session,
            project_id=uuid.uuid4(),
            workflow_type=WorkflowType.SIGN,
            workflow_id=wf,
            step_order=order,
            step_role="REVIEWER",
            state=WorkflowProgressState.PENDING,
            actor_user_id=uuid.uuid4(),
        )
    await db_session.commit()

    total = await db_session.scalar(select(func.count()).select_from(WorkflowProgress))
    assert total == 3
