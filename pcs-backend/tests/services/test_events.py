"""事件骨架 emit_event / listener / 幂等去重 (P7 Sprint 4 Task S4-0).

D4 裁决 4A: 业务模块通过 emit_event 发事件, **不直接调 state_machine**;
状态机保持单一权威, 只是触发路径事件化。

本模块锁定四件事:
1. 派发: emit_event 按注册顺序调用 listener, 传入 before/after/payload
2. 幂等: 同一 event_id 重复投递 → listener 一次都不再被调用
3. 冲突: 同一 event_id 携带不同 payload → 显式报错, 不静默按先到者处理
4. 快照: before 走 deepcopy, 嵌套结构不被后续修改串改
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.services.events import (
    clear_listeners,
    emit_event,
    register_listener,
    restore_listeners,
    snapshot_listeners,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """listener 是模块级注册表 — 每个测试清空, 防跨测试污染."""
    snap = snapshot_listeners()
    yield
    restore_listeners(snap)


# ---------------------------------------------------------------------------
# 1. 派发
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_calls_registered_listener(db_session: AsyncSession):
    got: list[dict] = []

    async def listener(event):
        got.append(event)

    register_listener("design_replaced", listener)
    eid = uuid.uuid4()
    await emit_event(
        db_session, "design_replaced", event_id=eid,
        before={"kw": 100.0}, after={"kw": 112.0},
    )
    assert len(got) == 1
    assert got[0]["event_id"] == eid
    assert got[0]["before"] == {"kw": 100.0}
    assert got[0]["after"] == {"kw": 112.0}


@pytest.mark.asyncio
async def test_emit_calls_listeners_in_registration_order(
    db_session: AsyncSession,
):
    order: list[str] = []

    async def first(event):
        order.append("first")

    async def second(event):
        order.append("second")

    register_listener("evt", first)
    register_listener("evt", second)
    await emit_event(db_session, "evt", event_id=uuid.uuid4())

    assert order == ["first", "second"]


@pytest.mark.asyncio
async def test_emit_passes_extra_payload(db_session: AsyncSession):
    got: list[dict] = []

    async def listener(event):
        got.append(event)

    register_listener("evt", listener)
    await emit_event(
        db_session, "evt", event_id=uuid.uuid4(),
        equipment_id="EQ-1", diff={"a": 1},
    )
    assert got[0]["equipment_id"] == "EQ-1"
    assert got[0]["diff"] == {"a": 1}


@pytest.mark.asyncio
async def test_emit_with_no_listener_is_noop(db_session: AsyncSession):
    """无人监听不应报错 (事件先落幂等表, listener 后续再注册)."""
    await emit_event(db_session, "nobody_listens", event_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# 2. 幂等
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_event_id_does_not_redispatch(
    db_session: AsyncSession,
):
    """同一 event_id 重投 → listener 一次都不再被调用 (影响 0 行)."""
    calls: list[int] = []

    async def listener(event):
        calls.append(1)

    register_listener("evt", listener)
    eid = uuid.uuid4()

    await emit_event(db_session, "evt", event_id=eid)
    await emit_event(db_session, "evt", event_id=eid)
    await emit_event(db_session, "evt", event_id=eid)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_different_event_ids_both_dispatch(
    db_session: AsyncSession,
):
    calls: list[int] = []

    async def listener(event):
        calls.append(1)

    register_listener("evt", listener)
    await emit_event(db_session, "evt", event_id=uuid.uuid4())
    await emit_event(db_session, "evt", event_id=uuid.uuid4())

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_idempotency_survives_module_reload_semantics(
    db_session: AsyncSession,
):
    """幂等凭据在 DB 里 — 清 listener 重注册后重投仍不应再派发.

    这正是选独立 event_idempotency 表 (而非内存) 的理由: 内存态重启即失效。
    """
    eid = uuid.uuid4()

    async def listener_a(event):
        pass

    register_listener("evt", listener_a)
    await emit_event(db_session, "evt", event_id=eid)

    # 模拟进程重启: listener 全丢, 重新注册后重投
    clear_listeners()
    calls: list[int] = []

    async def listener_b(event):
        calls.append(1)

    register_listener("evt", listener_b)
    await emit_event(db_session, "evt", event_id=eid)

    assert calls == []


# ---------------------------------------------------------------------------
# 3. payload_hash 冲突
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_event_id_different_payload_raises(
    db_session: AsyncSession,
):
    """同 event_id 不同 payload = 上游 bug → 显式报错, 不静默吞掉."""
    eid = uuid.uuid4()
    await emit_event(
        db_session, "evt", event_id=eid, after={"kw": 100.0}
    )
    with pytest.raises(PcsError) as exc:
        await emit_event(
            db_session, "evt", event_id=eid, after={"kw": 999.0}
        )
    assert exc.value.code == "EVENT_ID_CONFLICT"
    assert exc.value.status == 409


@pytest.mark.asyncio
async def test_conflict_does_not_redispatch(
    db_session: AsyncSession,
):
    """冲突抛错时 listener 也不应被调用."""
    calls: list[int] = []

    async def listener(event):
        calls.append(1)

    register_listener("evt", listener)
    eid = uuid.uuid4()
    await emit_event(db_session, "evt", event_id=eid, after={"kw": 1.0})
    with pytest.raises(PcsError):
        await emit_event(db_session, "evt", event_id=eid, after={"kw": 2.0})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_identical_payload_is_not_a_conflict(
    db_session: AsyncSession,
):
    """payload 完全相同 → 是幂等重投, 不是冲突 (不抛错)."""
    calls: list[int] = []

    async def listener(event):
        calls.append(1)

    register_listener("evt", listener)
    eid = uuid.uuid4()
    payload = {"kw": 100.0, "nested": {"a": [1, 2]}}
    await emit_event(db_session, "evt", event_id=eid, after=payload)
    await emit_event(db_session, "evt", event_id=eid, after=payload)

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# 4. before 快照保真
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_before_snapshot_is_deep_copied(db_session: AsyncSession):
    """before 走 deepcopy — 后续改原对象不得串改已存快照.

    浅拷贝在嵌套 dict/list 下会串: 事件存的是引用, 调用方改内层,
    快照跟着变 → P8 反向恢复拿到的是被污染的值。
    """
    async def listener(event):
        pass

    register_listener("evt", listener)
    original = {"design": {"kw": 100.0, "tags": ["a", "b"]}}
    await emit_event(
        db_session, "evt", event_id=uuid.uuid4(), before=original
    )

    # 调用方事后修改原对象 (模拟 ORM 对象被复用/改写)
    original["design"]["kw"] = 999.0
    original["design"]["tags"].append("c")

    from app.models.system import EventIdempotency  # noqa: PLC0415

    row = (
        await db_session.execute(select(EventIdempotency))
    ).scalars().one()
    assert row.before_json == {
        "design": {"kw": 100.0, "tags": ["a", "b"]}
    }


@pytest.mark.asyncio
async def test_before_defaults_to_none(db_session: AsyncSession):
    """不传 before → 存 NULL, 不报错 (非覆盖型事件不需要快照)."""
    from app.models.system import EventIdempotency  # noqa: PLC0415

    await emit_event(db_session, "evt", event_id=uuid.uuid4())
    row = (
        await db_session.execute(select(EventIdempotency))
    ).scalars().one()
    assert row.before_json is None


# ---------------------------------------------------------------------------
# 5. 幂等表结构
# ---------------------------------------------------------------------------


def test_event_idempotency_table_columns():
    from app.models.system import EventIdempotency  # noqa: PLC0415

    cols = {c.name for c in EventIdempotency.__table__.columns}
    assert {"event_id", "event_type", "payload_hash", "before_json",
            "processed_at"} <= cols
    # event_id 必须是主键 — 天然去重
    assert EventIdempotency.__table__.columns["event_id"].primary_key


@pytest.mark.asyncio
async def test_idempotency_row_written(db_session: AsyncSession):
    from app.models.system import EventIdempotency  # noqa: PLC0415

    eid = uuid.uuid4()
    await emit_event(
        db_session, "design_replaced", event_id=eid, before={"kw": 1.0}
    )
    row = (
        await db_session.execute(
            select(EventIdempotency).where(EventIdempotency.event_id == eid)
        )
    ).scalar_one()
    assert row.event_type == "design_replaced"
    assert row.payload_hash
