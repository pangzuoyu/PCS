"""`GET /streams/{id}/review-log` —— P9B-4 紧急批次 T6（TODO-112）。

## 裁决条件 2：必须有**正向**测试

守卫测试证明「越权被拒（404）」；**本文件必须证明「有权限时能读到正确的
记录」（200 + 正确的 transition 列表）**。两个测试**目标相反** ⇒
只写守卫测试的话，这个端点可能永远返回空数组而测试仍然绿。

## 裁决条件 3：范围

只做「读 review-log」—— 不加导出 / 管理员视角 / 时间筛选 / 分页。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StateTransition
from app.models.project import Project, Stream, Workspace
from app.models.system import AuditLog
from app.services.state_machine import TRANSITION_AUDIT_ACTION

pytestmark = pytest.mark.asyncio


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="review-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "review-designer")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="校核记录测试",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession):
    async def _make(project: Project) -> Stream:
        stream = Stream(
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            stream_name=f"S-{uuid.uuid4().hex[:6]}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


async def _audit(
    db: AsyncSession,
    *,
    stream_id: uuid.UUID,
    transition: str,
    user_id: uuid.UUID | None = None,
    reason: str | None = None,
    occurred_at=None,
) -> AuditLog:
    """造一条审计行 —— **动作名从状态机自己的映射派生**，不手抄。

    ## ⚠️ 为什么不能手抄 `action="RECORD_TRANSITION"`（bug-2146）

    状态机**每次转移只写一行**审计，其 `action` 由
    `state_machine.TRANSITION_AUDIT_ACTION[transition]` 决定：

    | transition | action |
    |---|---|
    | `SUBMIT_FOR_CHECK` | `RECORD_TRANSITION` |
    | `PASS_CHECK` | **`APPROVAL_STEP_PASSED`** |
    | `REJECT_CHECK` | **`APPROVAL_STEP_REJECTED`** |

    ⇒ 手抄一个动作名当**所有**转移的形状 ⇒ fixture 造出**生产中不存在的行**
    ⇒ 端点的过滤口径一旦与状态机漂移，测试**照样绿**（这正是本文件原来的病）。
    ⇒ fixture 必须**从真正的写入方派生**。
    """
    action = TRANSITION_AUDIT_ACTION[StateTransition(transition)]
    row = AuditLog(
        action=action.value,
        resource_type="streams",
        resource_id=str(stream_id),
        user_id=user_id,
        detail_json={
            "from": "DRAFT",
            "to": "IN_APPROVAL",
            "transition": transition,
            "reason": reason,
            "role": "DESIGNER",
        },
    )
    if occurred_at is not None:
        row.occurred_at = occurred_at
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 正向（裁决条件 2：证明「能读到」，不只是 404）
# ---------------------------------------------------------------------------


async def test_review_log_returns_only_review_transitions(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers, db_session
):
    """只返回 SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK 三条，
    **不含**其它状态转移（如 INITIATE_CHANGE）—— 最小暴露原则。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    stream = await make_stream(project)

    await _audit(db_session, stream_id=stream.stream_id, transition="SUBMIT_FOR_CHECK")
    await _audit(db_session, stream_id=stream.stream_id, transition="PASS_CHECK")
    await _audit(db_session, stream_id=stream.stream_id, transition="REJECT_CHECK")
    await _audit(db_session, stream_id=stream.stream_id, transition="INITIATE_CHANGE")
    await _audit(db_session, stream_id=stream.stream_id, transition="MARK_STALE")

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 3, body
    assert sorted(item["transition"] for item in body) == [
        "PASS_CHECK",
        "REJECT_CHECK",
        "SUBMIT_FOR_CHECK",
    ]


async def test_review_log_returns_check_verdicts_written_with_their_real_actions(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers, db_session
):
    """**回归钉子**（bug-2146）：校对通过 / 驳回两行**必须**返回。

    状态机给这两个转移写的审计动作**不是** `RECORD_TRANSITION`，而是
    `APPROVAL_STEP_PASSED` / `APPROVAL_STEP_REJECTED`
    （`state_machine.TRANSITION_AUDIT_ACTION`）。

    ⇒ 端点若按 `action == "RECORD_TRANSITION"` 过滤 ⇒ 这两行被吞 ⇒
    **静默**地只返回「提交校对」一条（200 + 部分列表，**不报错**）。

    ⇒ 这个测试用**真实的**动作值写行（fixture 从状态机映射派生）⇒
    只要端点的动作白名单再漂移一次，它就红。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    stream = await make_stream(project)

    # ⚠️ 三行**给不同的时间戳** —— `audit_logs.occurred_at` 是
    #    `server_default=now()`（**事务**时间戳）⇒ 同一事务里写的多行**时间相同**
    #    ⇒ 排序的次级键是随机 `audit_id` ⇒ 同一事务内顺序**任意**。
    #    （生产里每次转移各自提交 ⇒ 时间不同 ⇒ 顺序确定；这里给不同时间戳以免
    #       断言落在「任意顺序」上而变成假绿。）
    import datetime as dt

    base = dt.datetime(2026, 11, 9, 10, 0, 0)
    await _audit(
        db_session, stream_id=stream.stream_id, transition="SUBMIT_FOR_CHECK",
        occurred_at=base,
    )
    await _audit(
        db_session, stream_id=stream.stream_id, transition="PASS_CHECK",
        occurred_at=base + dt.timedelta(minutes=1),
    )
    await _audit(
        db_session, stream_id=stream.stream_id, transition="REJECT_CHECK",
        occurred_at=base + dt.timedelta(minutes=2),
    )

    # ⚠️ 前置断言：这三条审计行**确实**用的是三个**不同**的动作名
    #    （否则下面的断言可能是被同一个错误常量喂出来的假绿）。
    actions = (
        await db_session.execute(
            select(AuditLog.action).where(AuditLog.resource_id == str(stream.stream_id))
        )
    ).scalars().all()
    assert set(actions) == {
        "RECORD_TRANSITION",
        "APPROVAL_STEP_PASSED",
        "APPROVAL_STEP_REJECTED",
    }, actions

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [item["transition"] for item in body] == [
        "SUBMIT_FOR_CHECK",
        "PASS_CHECK",
        "REJECT_CHECK",
    ], body


async def test_review_log_is_sorted_by_occurred_at_asc(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers, db_session
):
    """按 `occurred_at` **升序**返回（页面按时间正序读）。"""
    import datetime as dt

    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    stream = await make_stream(project)

    base = dt.datetime(2026, 11, 1, 8, 0, 0)
    await _audit(
        db_session,
        stream_id=stream.stream_id,
        transition="REJECT_CHECK",
        occurred_at=base + dt.timedelta(hours=2),
    )
    await _audit(
        db_session,
        stream_id=stream.stream_id,
        transition="SUBMIT_FOR_CHECK",
        occurred_at=base,
    )
    await _audit(
        db_session,
        stream_id=stream.stream_id,
        transition="PASS_CHECK",
        occurred_at=base + dt.timedelta(hours=1),
    )

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [item["transition"] for item in body] == [
        "SUBMIT_FOR_CHECK",
        "PASS_CHECK",
        "REJECT_CHECK",
    ]


async def test_review_log_carries_operator_and_reason(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers, db_session
):
    """`operator` 是审计里的 actor，`detail` 是转移附带的 reason（驳回理由）。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    stream = await make_stream(project)

    await _audit(
        db_session,
        stream_id=stream.stream_id,
        transition="REJECT_CHECK",
        user_id=designer_user_id,
        reason="组成超差",
    )

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    item = r.json()[0]
    assert item["operator"] == str(designer_user_id)
    assert item["detail"] == "组成超差"
    assert item["occurred_at"]


async def test_review_log_of_a_stream_without_transitions_is_empty_list(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers
):
    """无校核记录 ⇒ **200 + []**（不是 404）—— 端点存在，只是没记录。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


async def test_review_log_ignores_other_streams_records(
    strict_client, make_project, make_stream, grant_project, designer_user_id,
    designer_headers, db_session
):
    """别的物流的审计行**不得**混进来（`resource_id` 精确匹配）。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="review-designer")
    mine = await make_stream(project)
    other = await make_stream(project)

    await _audit(db_session, stream_id=mine.stream_id, transition="SUBMIT_FOR_CHECK")
    await _audit(db_session, stream_id=other.stream_id, transition="PASS_CHECK")

    r = await strict_client.get(
        f"/api/v1/streams/{mine.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["transition"] == "SUBMIT_FOR_CHECK"


# ---------------------------------------------------------------------------
# 负向
# ---------------------------------------------------------------------------


async def test_review_log_of_another_project_stream_is_404(
    strict_client, make_project, make_stream, designer_headers, db_session
):
    """跨项目 ⇒ 404（与「不存在」同形 —— `SIM_STREAM_NOT_FOUND`）。"""
    project = await make_project()
    stream = await make_stream(project)
    await _audit(db_session, stream_id=stream.stream_id, transition="SUBMIT_FOR_CHECK")

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}/review-log", headers=designer_headers
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


async def test_review_log_of_unknown_stream_is_404(
    strict_client, designer_headers
):
    """不存在的物流 ⇒ 404（与跨项目**同码同形**）。"""
    r = await strict_client.get(
        f"/api/v1/streams/{uuid.uuid4()}/review-log", headers=designer_headers
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"
