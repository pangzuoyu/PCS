"""P9A-OBS-004 验收：写入 → 可查的 p99 ≤ 500ms（ADR-0047 §②）。

## 这条测试**测的是什么、不测什么**

测的是 ADR-0047 §② 那个结构性决定的**代价**：同步写把「一次业务事务」变成
「一次业务事务 + 一次 INSERT」，观测行的可见延迟因此等于一个事务往返。
异步（ARQ）写法会把延迟变成「已提交但未入队」+「入队但队列慢」的叠加，
且上限不可控 —— 那才是观测层不可信的开始。

**不测的是生产 p99。** 这里是内存 SQLite，往返是微秒级；生产的真实数字
取决于网络与 DB。测试的价值在于：① 打印实测值而不是只断言通过；
② 钉住「写入与读在同一事务可见」这个性质（读不到就是 0 行）；
③ 一旦有人把写入改成异步管道，`p99` 会随队列入队延迟放大而红。

## 计划验收清单第 ③ 条的处置

计划写「cron 驱动的变更也有观测」。实测 **ADR-0047 §① 的三个写入点里没有
cron** —— `cia_mark_stale` 由 ARQ cron 驱动，但它是**记录状态**变更，
不是工作流步骤推进；把它加进来就成了 ADR-0047 §后果 明令禁止的「第四类工作流」。

⇒ 本轮的正确形态是：**service 直调也写观测**（cron/事件驱动的调用路径正是
service 直调）。该性质由 B2 的 `test_sign_step_writes_progress_via_service_not_api`
与本文件的 service 直调覆盖，不新增 cron 写入点。
"""
from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress
from app.services.workflow_progress_writer import record_step

pytestmark = [pytest.mark.asyncio, pytest.mark.slow]

#: SPEC P9A-OBS-004 的上界。
P99_BUDGET_MS = 500.0

#: 迭代次数。20 次够算 p99（= 最慢那次），也够让一次 GC 抖动落在分布里。
ITERATIONS = 20


def _p99(samples: list[float]) -> float:
    """p99。样本量小时取最慢那次（保守方向）。"""
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * 0.99))
    return ordered[index]


async def _write_then_read(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    workflow_id: uuid.UUID,
    step_order: int,
    workflow_type: WorkflowType,
) -> float:
    """写一行观测 + 立刻读回，返回「写入调用 → 读得到」的毫秒数。

    **计时含 commit**：SPEC 的口径是「流程状态变更到持久化」，
    只量 flush 会漏掉真正的持久化等待。

    ⚠️ **`workflow_type` 必须传进来**（2026-10-21 修）：原实现把
    `WorkflowType.SIGN` 写死在写入与查询两处 ⇒ 上面的 `@parametrize`
    三个用例**测的都是 SIGN** —— 用例名说「三类工作流逐类」，代码只跑一类。
    这正是本仓反复付过代价的形状：**参数化装饰了一个从未生效的变量**
    （见 `.wolf/cerebrum.md`「守卫测试会被它守护的那行注释骗过」）。
    """
    started = time.perf_counter()
    await record_step(
        session=db,
        project_id=project_id,
        workflow_type=workflow_type,
        workflow_id=workflow_id,
        step_order=step_order,
        step_role="CHECKER",
        state=WorkflowProgressState.IN_PROGRESS,
        actor_user_id=uuid.uuid4(),
    )
    await db.commit()

    rows = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == workflow_type,
                WorkflowProgress.workflow_id == workflow_id,
                WorkflowProgress.step_order == step_order,
            )
        )
    ).scalars().all()
    assert rows, "写完立刻读不到 —— 观测层不可信，延迟再低也没意义"
    return (time.perf_counter() - started) * 1000.0


@pytest.mark.parametrize(
    "workflow_type",
    [WorkflowType.SIGN, WorkflowType.CHANGE_NOTICE, WorkflowType.CUSTOMER_APPROVAL_PROXY],
)
async def test_observed_p99_under_500ms(db_session, workflow_type):
    """三类工作流逐类：写入 → 可查的 p99 ≤ 500ms。**必须打印实测值。"""
    project_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    samples: list[float] = []

    for i in range(ITERATIONS):
        samples.append(
            await _write_then_read(
                db_session,
                project_id=project_id,
                workflow_id=workflow_id,
                step_order=i + 1,
                workflow_type=workflow_type,
            )
        )

    p99 = _p99(samples)
    print(
        f"\n[P9A-OBS-004] {workflow_type.value}: "
        f"n={len(samples)} min={min(samples):.3f}ms "
        f"median={sorted(samples)[len(samples) // 2]:.3f}ms p99={p99:.3f}ms "
        f"budget={P99_BUDGET_MS}ms"
    )
    assert p99 <= P99_BUDGET_MS, (
        f"{workflow_type.value} 观测延迟 p99={p99:.1f}ms 超过 {P99_BUDGET_MS}ms"
    )


async def test_all_three_workflow_types_are_writable(db_session):
    """ADR-0047 §① 的三个写入点都能写 —— 缺一个就是一类工作流没有观测。

    这条不量时间，量**覆盖面**：时间再低，漏掉的工作流在甘特图上照样是空白。
    """
    for wf_type in WorkflowType:
        await record_step(
            session=db_session,
            project_id=uuid.uuid4(),
            workflow_type=wf_type,
            workflow_id=uuid.uuid4(),
            step_order=1,
            step_role="CHECKER",
            state=WorkflowProgressState.IN_PROGRESS,
            actor_user_id=uuid.uuid4(),
        )
    await db_session.commit()

    rows = (await db_session.execute(select(WorkflowProgress))).scalars().all()
    assert {r.workflow_type for r in rows} == set(WorkflowType)
