"""AI 审计的**入队**与**幂等写库**（P10-A · Task T10 · Review Focus #3）。

## 为什么幂等是硬要求

⚠️ **ARQ 0.28 只对 `Retry` 异常重试**（其余当场判死）⇒
「`max_tries=5` ⇒ 重试必然发生」**不成立**（本仓 `MAX_TRIES = 3`，
见 `app/workers/worker.py`）⇒ 幂等**不能**靠「反正会重试」来兜底：
它要么来自**业务侧的重复调用**（重投语义），要么来自
**我们自己在任务里主动抛 `Retry`**（评审 #6 · 2026-11-12）。
⇒ 幂等测试**直接调它两次**来模拟重投（不依赖 ARQ 的重试机制）。

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

    （重投语义 ⇒ 幂等不是「锦上添花」。）
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


# === 评审 #6 / #21（代码部分）/ #24（2026-11-12 评审修复批） ===


async def test_write_failure_raises_retry_instead_of_swallowing(
    worker_ctx, monkeypatch
) -> None:
    """⚠️ **评审 #6** —— 写库失败 ⇒ 必须抛 `Retry`（**有界**重试），不是吞掉。

    ⚠️ **ARQ 0.28 只对 `Retry` 异常重试**（其余当场判死；见
    `app/workers/worker.py` 的注释与
    `docs/solutions/framework-integration-issues/arq-028-worker-silent-failure-modes.md`）
    ⇒ 旧实现把异常吞掉 ⇒ ARQ 认为 job **成功** ⇒ job 被删除
    ⇒ **那一次请求的审计行永久丢失**，而请求早就返回 501 了
    ⇒ 审计表对那次调用**完全失明**。
    """
    from arq import Retry

    import app.workers.ai_audit_tasks as mod

    async def boom(session, row):
        raise RuntimeError("DB 写炸了")

    monkeypatch.setattr(mod, "_insert_row", boom)

    with pytest.raises(Retry):
        await write_ai_audit_log(worker_ctx, **_fields())


async def test_write_failure_stops_retrying_after_the_last_attempt(
    worker_ctx, monkeypatch
) -> None:
    """⚠️ **评审 #6** —— 重试**有界**：次数用完 ⇒ 不再抛（最后一次失败留痕）。

    ⇒ 没有界的话 ⇒ 无限重试 ⇒ 队列被一个坏任务占死。
    """
    import app.workers.ai_audit_tasks as mod
    from app.workers.worker import MAX_TRIES

    async def boom(session, row):
        raise RuntimeError("DB 写炸了")

    monkeypatch.setattr(mod, "_insert_row", boom)

    ctx = {**worker_ctx, "job_try": MAX_TRIES}

    await write_ai_audit_log(ctx, **_fields())  # 不得抛


async def test_schema_error_is_logged_with_an_upgrade_hint(
    worker_ctx, monkeypatch, caplog
) -> None:
    """⚠️ **评审 #21（代码部分）** —— 「目标库没迁移」要**说人话**。

    旧实现把所有写失败都归成一条 WARNING ⇒ 运维看到的是
    「审计失败」而不知道该跑 `alembic upgrade head` ⇒ 而审计表**一直是空的**。
    """
    from sqlalchemy.exc import ProgrammingError

    import app.workers.ai_audit_tasks as mod

    async def boom(session, row):
        raise ProgrammingError(
            "INSERT", {}, Exception('column "model_version" does not exist')
        )

    monkeypatch.setattr(mod, "_insert_row", boom)

    with caplog.at_level("ERROR"):
        # ⚠️ `job_try` 已是最后一次 ⇒ **不抛**（重试有界）⇒ 只看日志。
        await write_ai_audit_log({**worker_ctx, "job_try": 99}, **_fields())

    assert "alembic upgrade head" in caplog.text, caplog.text


async def test_enqueue_reuses_one_pool_instead_of_one_per_request(monkeypatch) -> None:
    """⚠️ **评审 #20** —— 连接池**进程级复用**，不是每个请求建一个又拆一个。

    旧实现每个 AI 请求都 `create_pool` + `aclose` ⇒ 每次付一次 TCP 连接
    + AUTH ⇒ 而这条路径**注定**是未来的热路径。
    """
    import app.services.ai.arq_queue as arq_queue

    created = {"n": 0}

    class _FakePool:
        async def enqueue_job(self, *args, **kwargs):
            return object()

        async def aclose(self):
            return None

    async def fake_create_pool():
        created["n"] += 1
        return _FakePool()

    arq_queue._reset_pool_cache()  # 每个用例从干净状态开始
    monkeypatch.setattr(arq_queue, "_create_pool", fake_create_pool)

    await arq_queue.enqueue_ai_audit_log(**_fields())
    await arq_queue.enqueue_ai_audit_log(**_fields())

    assert created["n"] == 1, f"连接池建了 {created['n']} 次 ⇒ 没有复用"
    arq_queue._reset_pool_cache()


async def test_enqueue_is_bounded_in_time(monkeypatch) -> None:
    """⚠️ **评审 #16** —— Redis 挂 ⇒ 入队**必须很快失败**，不能拖住请求。

    ⚠️ ARQ 的 `create_pool` 默认 `conn_retries=5` + 1 秒间隔 ⇒ Redis 不可达时
    一次入队要拖 **~10 秒** ⇒ 而入队是在中间件的 `finally` 里 await 的
    ⇒ **HTTP 连接被钉住 10 秒**（客户端早拿到 501 了，服务端还在等）。
    ⇒ 池设置 `conn_retries=0`（快速失败）+ 入队**超时兜底**。
    """
    import asyncio

    import app.services.ai.arq_queue as arq_queue

    class _HangingPool:
        async def enqueue_job(self, *args, **kwargs):
            await asyncio.sleep(3600)
            return None

        async def aclose(self):
            return None

    async def fake_create_pool():
        return _HangingPool()

    arq_queue._reset_pool_cache()  # 每个用例从干净状态开始
    monkeypatch.setattr(arq_queue, "_create_pool", fake_create_pool)

    started = asyncio.get_running_loop().time()
    # ⚠️ **测试自己也要有上界** —— 否则旧实现（无超时）会让这条用例**挂住**
    # （而不是失败）⇒ 旧实现下这里抛 TimeoutError ⇒ 用例红。
    try:
        ok = await asyncio.wait_for(
            arq_queue.enqueue_ai_audit_log(**_fields()),
            timeout=arq_queue.ENQUEUE_TIMEOUT_S + 3,
        )
    except TimeoutError:
        pytest.fail("入队没有超时兜底 ⇒ 请求连接会被无限期钉住")
    elapsed = asyncio.get_running_loop().time() - started

    assert ok is False
    assert elapsed < arq_queue.ENQUEUE_TIMEOUT_S + 1.0, (
        f"入队拖了 {elapsed:.1f}s ⇒ 请求连接被钉住"
    )
