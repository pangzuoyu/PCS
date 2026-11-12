"""AI 审计的**入队**与**幂等写库**（P10-A · Task T10 · Review Focus #3）。

## 为什么幂等是硬要求

ARQ 默认 `max_tries=5`（本批不显式改）⇒ **重试必然发生** ⇒
写库若不幂等 ⇒ 一次请求留下 **N 条**审计 ⇒ 审计表被灌水。
⇒ 幂等测试**直接调它两次**来模拟重试（不依赖 ARQ 的重试机制）。

## 两条容易写错的

1. **PG 与 SQLite 的方言差异** —— `ON CONFLICT DO NOTHING` 在 SQLite 上
   **不可用** ⇒ 单测库（内存 SQLite）必须走「先查后插 + catch
   `IntegrityError`」分支 ⇒ 否则单测会炸或**永远绿**（见下）。
2. **`IntegrityError` 分支在单线程里造不出来** —— 第二次调用时查询确实
   查到了 ⇒ 走的是「跳过」分支 ⇒ 根本没碰 `IntegrityError`
   ⇒ **假测试**。⇒ 必须 monkeypatch 掉查询，让它返回空（模拟「查的时候
   不存在」），再让插入抛 `IntegrityError`（模拟「插的时候已经存在」）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.system import AiAuditLog
from app.services.ai.arq_queue import enqueue_ai_audit_log
from app.workers.ai_audit_tasks import write_ai_audit_log


def _fields(request_id: str | None = None) -> dict:
    """一行 AI 审计的字段（形状与中间件组装的一致）。"""
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "client_request_id": None,
        "endpoint": "/api/v1/ai/intent",
        "status_code": 501,
        "duration_ms": 3,
        "sanitized_request_hash": "sha256:deadbeef",
        "response_summary": "AI_NOT_IMPLEMENTED",
        "model_version": None,
        "user_id": None,
    }


@pytest.fixture
def worker_ctx(db_engine) -> dict:
    """ARQ ctx（带 session_factory）—— 与 `worker.py::_on_startup` 同款。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return {"session_factory": factory}


async def _count(db) -> int:
    return int((await db.execute(select(func.count()).select_from(AiAuditLog))).scalar_one())


async def test_audit_write_is_idempotent(db_session, worker_ctx) -> None:
    """⚠️ **Review Focus #3** —— 同一 request_id 写两次 ⇒ 只有一行。

    （ARQ 默认 max_tries=5 ⇒ 重试必然发生 ⇒ 幂等不是「锦上添花」。）
    """
    fields = _fields()

    await write_ai_audit_log(worker_ctx, **fields)
    await write_ai_audit_log(worker_ctx, **fields)

    assert await _count(db_session) == 1


async def test_audit_write_creates_distinct_rows_for_distinct_requests(
    db_session, worker_ctx
) -> None:
    """不同 request_id ⇒ 两行（幂等不是「只写一行」）。"""
    await write_ai_audit_log(worker_ctx, **_fields())
    await write_ai_audit_log(worker_ctx, **_fields())

    assert await _count(db_session) == 2


async def test_enqueue_failure_is_swallowed(monkeypatch) -> None:
    """Redis 挂 ⇒ enqueue 返回 False，**不抛**（降级）。

    ⚠️ 端点在业务链路上 ⇒ 入队失败抛 503 ⇒ **AI 端点会因为审计挂掉**
    ⇒ 审计必须降级。
    """
    import app.services.ai.arq_queue as arq_queue

    async def boom(*args, **kwargs):
        raise RuntimeError("Redis 挂了")

    monkeypatch.setattr(arq_queue, "_create_pool", boom)

    assert await enqueue_ai_audit_log(**_fields()) is False


async def test_task_is_registered_in_worker_functions() -> None:
    """⚠️ ARQ 对**未注册**的函数名不报错 ⇒ job 静静躺着 ⇒ 棘轮会抓。

    ⚠️ **与既有棘轮的关系**：仓里已有
    `tests/workers/test_worker_registers_all_enqueued_tasks.py` 断言
    「入队的 ⊆ 已注册的」（通用）；本条是**具体的**断言
    （`write_ai_audit_log` 在 `WorkerSettings.functions` 里）⇒ 两条不重复。
    """
    from app.workers.worker import WorkerSettings

    names = {fn.__name__ for fn in WorkerSettings.functions}
    assert "write_ai_audit_log" in names, sorted(names)


async def test_audit_write_swallows_integrity_error_on_sqlite(
    db_session, worker_ctx, monkeypatch
) -> None:
    """⚠️ SQLite 分支是「先查后插」⇒ 并发下第二个插入抛 `IntegrityError`
    ⇒ 必须 catch 掉，不算失败。

    ⚠️ **单线程里造不出这个竞态** ⇒ 必须**显式构造**：monkeypatch 掉查询，
    让它返回空（模拟「查的时候不存在」），再让插入抛 `IntegrityError`
    （模拟「插的时候已经存在」）⇒ 断言 `write_ai_audit_log` **不抛**。
    ⇒ 不这样构造的话，这条测试**永远绿** ⇒ **假测试**。
    """
    import app.workers.ai_audit_tasks as task_mod

    await write_ai_audit_log(worker_ctx, **_fields())

    # 让「查」永远查不到 ⇒ 走插入分支
    async def fake_find_existing(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return None

    monkeypatch.setattr(task_mod, "_find_existing", fake_find_existing)

    async def fake_insert_row(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(task_mod, "_insert_row", fake_insert_row)

    # ⇒ 不抛
    await write_ai_audit_log(worker_ctx, **_fields())
    assert await _count(db_session) == 1


def test_audit_write_uses_the_pg_conflict_clause_on_postgres() -> None:
    """PG 分支走 `ON CONFLICT DO NOTHING`（方言级断言）。

    ⚠️ 单测跑在内存 SQLite 上 ⇒ 直接断言**语句形状**（PG dialect 的
    `ON CONFLICT ... DO NOTHING` + 冲突目标 `request_id`）。
    """
    from app.workers.ai_audit_tasks import _build_insert

    stmt = _build_insert(
        {
            "agent_id": uuid.uuid4(),
            "operation": "AI_REQUEST",
            "request_id": "req-1",
        },
        is_postgres=True,
    )

    text = str(stmt)
    assert "ON CONFLICT" in text
    assert "request_id" in text
    assert "DO NOTHING" in text


def test_audit_write_falls_back_to_the_orm_insert_on_sqlite() -> None:
    """非 PG ⇒ 走 ORM 的 `add()`（SQLite 上 `ON CONFLICT` 不可用）。"""
    from app.models.system import AiAuditLog
    from app.workers.ai_audit_tasks import _build_insert

    row = _build_insert(
        {
            "agent_id": uuid.uuid4(),
            "operation": "AI_REQUEST",
            "request_id": "req-1",
        },
        is_postgres=False,
    )

    assert isinstance(row, AiAuditLog)
    assert row.request_id == "req-1"
