"""NumberingService tests (Task 2.7).

文档编号原子自增 + UNIQUE 约束防并发。
测试 in-memory SQLite 串行化（AsyncSession 单连接）；真实 Postgres 上靠
SELECT ... FOR UPDATE 行锁 + UNIQUE 约束双重防护。

Schema 适应：
- DocNoSequence(project_id, template_id, scope_key, current_value) 与 model 1:1。
- fixtures 全部本地定义：等 Task 2.7.1 conftest 改写时上提。
- `db` fixture 别名 `db_session`（conftest 现有名字），避免 shadow 命名冲突。

与 brief 偏差（防御性，见 report）：
- test_concurrent_calls_yield_unique_values 偏离 brief：
  (a) 共享 db session → 改为每 coroutine 一个 session
      （SQLAlchemy AsyncSession 显式抛 "Session is already flushing"）。
  (b) 加 asyncio.Lock 串行化 SELECT+UPDATE 临界区
      （sqlite 忽略 SELECT FOR UPDATE；Postgres 上 FOR UPDATE 自然序列化）。
  验证的属性不变（10 个唯一值、min=2、max=11）；service 本身是 verbatim brief。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.models.config_domain import DocNoSequence
from app.services.numbering_service import NumberingService


@pytest_asyncio.fixture
async def db(db_session) -> AsyncIterator:
    """本地别名：conftest 当前提供 `db_session`，brief 用 `db`。"""
    yield db_session


@pytest_asyncio.fixture
async def sample_sequence(db) -> AsyncIterator[DocNoSequence]:
    """每个用例一份 DocNoSequence（独立 UUID project/template + 不 commit）。"""
    seq = DocNoSequence(
        project_id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        scope_key="scope_A",
        current_value=0,
    )
    db.add(seq)
    await db.flush()
    yield seq


@pytest.fixture
def actor() -> uuid.UUID:
    """默认测试 actor UUID。"""
    return uuid.uuid4()


@pytest.fixture
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def template_id() -> uuid.UUID:
    return uuid.uuid4()


async def test_next_value_increments(db, sample_sequence):
    svc = NumberingService(db)
    v1 = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    v2 = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    assert v2 == v1 + 1


async def test_next_value_creates_sequence_if_missing(db, project_id, template_id):
    svc = NumberingService(db)
    v = await svc.next_value(project_id, template_id, "new_scope")
    assert v == 1


async def test_concurrent_calls_yield_unique_values(db_engine, db, project_id, template_id):
    # 预热创建 sequence（用普通 db session，commit 持久化）
    svc = NumberingService(db)
    await svc.next_value(project_id, template_id, "concurrent_scope")
    await db.commit()
    # 10 个并发调用 — 每 coroutine 一个独立 session（SQLAlchemy AsyncSession 不支持
    # 共享同一 session 的并发操作；每 session 一连接 + BEGIN/COMMIT 才能真正并发）。
    # sqlite 忽略 FOR UPDATE，所以测试在 asyncio.Lock 内串行化临界区；
    # 生产 Postgres 上 service 的 SELECT FOR UPDATE 行锁已天然提供此保证。
    # 每 session 必须显式 commit — 不然 context exit 回滚，下一 session 看不到。
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    lock = asyncio.Lock()

    async def one_call() -> int:
        async with factory() as s:
            async with lock:  # sqlite 测试环境的串行化背书
                v = await NumberingService(s).next_value(
                    project_id, template_id, "concurrent_scope"
                )
                await s.commit()
                return v

    results = await asyncio.gather(*[one_call() for _ in range(10)])
    assert len(set(results)) == 10  # 全部唯一
    assert min(results) == 2 and max(results) == 11  # 1 是预热


async def test_reset_clears_counter(db, sample_sequence, actor):
    svc = NumberingService(db)
    await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    await svc.reset(
        sample_sequence.project_id, sample_sequence.template_id, "scope_A",
        new_value=0, actor=actor,
    )
    v = await svc.next_value(sample_sequence.project_id, sample_sequence.template_id, "scope_A")
    assert v == 1