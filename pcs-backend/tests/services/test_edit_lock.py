"""编辑锁（Redis 层）测试 —— P9A-4 D1（ADR-0048 §①~⑤）。

## 为什么用真 Redis，不用 mock

锁的语义有三个**只有真 Redis 能证明**的性质：

1. **TTL 到期自动释放**（§③）—— `TTL key` 只返回「还剩多久」，证明不了
   「到期后会释放」；假时钟也 patch 不了 Redis 服务端的计时器。
   ⇒ 必须**真等过期**。
2. **compare-and-expire 续期**（§②）—— 续期必须是「值是我的才重置 TTL」的
   原子操作，否则他人的心跳能延长我的锁。
3. **跨会话互斥**（§①）—— 两个真实会话抢同一记录，第二个必须被拒。

⇒ 本文件用真 Redis（DB 9，与 broadcaster 测试同款隔离）。Redis 没起时
**skip**（不是绿）—— 看输出别误读。

## 降级语义（§⑤）

Redis 不可用 ⇒ **降级放行 + ERROR 日志 + 横幅**，不是 503。
「放行的是**体验**，拦住并发的是 DB 层」（D2 的 record_hash 比对）。
"""
from __future__ import annotations

import asyncio
import inspect
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as aioredis

from app.services.edit_lock import (
    DEFAULT_TTL_SECONDS,
    DEGRADED_MESSAGE,
    NO_CONFLICT_DETECTION_MESSAGE,
    EditLockService,
)

REDIS_URL = "redis://localhost:6379/9"
DEAD_REDIS_URL = "redis://127.0.0.1:6399/0"  # 无人监听


async def _redis_up() -> bool:
    """真 ping（⚠️ async 客户端的 ping() 返回协程 —— 不同步 await 它
    就等于没检查，fixture 永远不会 skip）。"""
    r = aioredis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
    try:
        await r.ping()
    except Exception:  # noqa: BLE001
        return False
    finally:
        await r.aclose()
    return True


@pytest_asyncio.fixture
async def real_redis():
    if not await _redis_up():
        pytest.skip("真 Redis 未运行（docker compose up redis）—— TTL/续期无法用 fake 证明")
    yield REDIS_URL


@pytest.fixture
async def lock_service(real_redis):
    svc = EditLockService(real_redis)
    try:
        yield svc
    finally:
        await svc.aclose()


def _rid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# ① acquire
# ---------------------------------------------------------------------------


async def test_acquire_grants_lock_to_first_caller(lock_service):
    """第一个调用者拿到锁。"""
    rid = _rid()
    me = uuid.uuid4()
    r = await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)
    assert r.success is True
    assert r.degraded is False
    assert r.holder is not None and r.holder.user_id == me
    assert r.ttl_seconds == DEFAULT_TTL_SECONDS


async def test_acquire_returns_holder_info_when_held(lock_service):
    """他人持锁 ⇒ 第二个调用者拿不到，且**拿到持锁人信息**（体验层的全部价值）。"""
    rid = _rid()
    me, other = uuid.uuid4(), uuid.uuid4()
    await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)

    r = await lock_service.acquire(
        record_type="cost_est_results", record_id=rid, user_id=other
    )
    assert r.success is False
    assert r.holder is not None
    assert r.holder.user_id == me, "必须告诉前端是谁持着锁"
    assert r.holder.acquired_at is not None


async def test_acquire_is_idempotent_for_the_same_holder(lock_service):
    """同一 holder 重复 acquire 不报错（前端重试 / 幂等刷新）。"""
    rid = _rid()
    me = uuid.uuid4()
    a = await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)
    b = await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)
    assert a.success is True and b.success is True
    assert b.holder is not None and b.holder.user_id == me


async def test_two_sessions_one_holder(real_redis):
    """E2E：两个**真实会话**（两个 service 实例 = 两个 Redis 连接）抢同一记录。"""
    rid = _rid()
    a = EditLockService(real_redis)
    b = EditLockService(real_redis)
    try:
        me, other = uuid.uuid4(), uuid.uuid4()
        r1 = await a.acquire(record_type="psychro_results", record_id=rid, user_id=me)
        r2 = await b.acquire(record_type="psychro_results", record_id=rid, user_id=other)
        assert r1.success is True
        assert r2.success is False
        assert r2.holder is not None and r2.holder.user_id == me
    finally:
        await a.aclose()
        await b.aclose()


# ---------------------------------------------------------------------------
# ② renew（compare-and-expire）
# ---------------------------------------------------------------------------


async def test_renew_extends_ttl_only_for_current_holder(lock_service):
    """⚠️ **他人的心跳不得延长我的锁**（§②）。"""
    rid = _rid()
    me, other = uuid.uuid4(), uuid.uuid4()
    await lock_service.acquire(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=2
    )
    await asyncio.sleep(1)

    r = await lock_service.renew(
        record_type="cost_est_results", record_id=rid, user_id=other, ttl_seconds=60
    )
    assert r.success is False, "他人续期竟然成功了 ⇒ 我的锁会被别人续命"

    # 我的锁不该被他的续期延长 ⇒ 2s 后应当过期
    await asyncio.sleep(1.5)
    assert await lock_service.is_held(
        record_type="cost_est_results", record_id=rid
    ) is False


async def test_renew_extends_ttl_for_the_holder(lock_service):
    """持有者续期 ⇒ TTL 被重置（否则 60s 心跳毫无意义）。"""
    rid = _rid()
    me = uuid.uuid4()
    await lock_service.acquire(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=2
    )
    await asyncio.sleep(1)
    r = await lock_service.renew(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=30
    )
    assert r.success is True
    await asyncio.sleep(1.5)
    assert await lock_service.is_held(
        record_type="cost_est_results", record_id=rid
    ) is True, "续期没有延长 TTL"


async def test_renew_rejects_expired_lock(lock_service):
    """锁已过期 ⇒ 续期失败（不能凭空复活一把没人持有的锁）。"""
    rid = _rid()
    me = uuid.uuid4()
    await lock_service.acquire(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=1
    )
    await asyncio.sleep(1.5)
    r = await lock_service.renew(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=30
    )
    assert r.success is False
    assert r.holder is None, "过期后没有持有者"


# ---------------------------------------------------------------------------
# ③ TTL 到期
# ---------------------------------------------------------------------------


async def test_lock_expires_after_ttl_without_heartbeat(lock_service):
    """TTL 到期 ⇒ 锁自动释放（§③）。

    ⚠️ **真等过期**：不查 TTL、不用假时钟（Redis 的 TTL 是服务端算的）。
    """
    rid = _rid()
    me = uuid.uuid4()
    await lock_service.acquire(
        record_type="cost_est_results", record_id=rid, user_id=me, ttl_seconds=2
    )
    assert await lock_service.is_held(record_type="cost_est_results", record_id=rid) is True
    await asyncio.sleep(3)
    assert await lock_service.is_held(record_type="cost_est_results", record_id=rid) is False


async def test_default_ttl_is_30_minutes():
    """别为了测试把默认值也改了 —— 生产仍须是 30 分钟（§②）。"""
    assert EditLockService.DEFAULT_TTL_SECONDS == 30 * 60
    assert DEFAULT_TTL_SECONDS == 30 * 60


async def test_heartbeat_is_60_seconds():
    """心跳 60s（TTL 的 1/30 余量，§②）。"""
    assert EditLockService.HEARTBEAT_SECONDS == 60


# ---------------------------------------------------------------------------
# ④ release（仅持有者）
# ---------------------------------------------------------------------------


async def test_release_is_owner_only(lock_service):
    """非持有者 release ⇒ 不得释放别人的锁。"""
    rid = _rid()
    me, other = uuid.uuid4(), uuid.uuid4()
    await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)

    r = await lock_service.release(
        record_type="cost_est_results", record_id=rid, user_id=other
    )
    assert r.success is False
    assert await lock_service.is_held(record_type="cost_est_results", record_id=rid) is True, (
        "他人的 release 把我的锁释放了"
    )


async def test_release_by_owner_frees_the_lock(lock_service):
    rid = _rid()
    me = uuid.uuid4()
    await lock_service.acquire(record_type="cost_est_results", record_id=rid, user_id=me)
    r = await lock_service.release(record_type="cost_est_results", record_id=rid, user_id=me)
    assert r.success is True
    assert await lock_service.is_held(record_type="cost_est_results", record_id=rid) is False


async def test_release_of_a_free_lock_is_a_no_op(lock_service):
    """释放一把不存在的锁 ⇒ 不报错（幂等）。"""
    r = await lock_service.release(
        record_type="cost_est_results", record_id=_rid(), user_id=uuid.uuid4()
    )
    assert r.success is False
    assert r.holder is None


# ---------------------------------------------------------------------------
# ⑤ 降级（Redis 不可用）
# ---------------------------------------------------------------------------


async def test_redis_down_warns_and_allows_not_503():
    """Redis 不可用 ⇒ **降级放行**（不是 503）+ ERROR 日志 + 横幅（§⑤）。

    ⚠️ 「放行的是体验，拦住并发的是 DB 层」—— 不是无锁放行。
    """
    svc = EditLockService(DEAD_REDIS_URL)
    try:
        r = await svc.acquire(
            record_type="cost_est_results", record_id=_rid(), user_id=uuid.uuid4()
        )
        assert r.degraded is True
        assert r.success is True, "降级时必须放行（体验层），不能把用户挡在门外"
        assert r.message is not None and DEGRADED_MESSAGE in r.message
    finally:
        await svc.aclose()


async def test_redis_down_degrades_renew_and_release():
    """降级对 renew / release 同样生效（不得抛 500）。"""
    svc = EditLockService(DEAD_REDIS_URL)
    try:
        rid = _rid()
        me = uuid.uuid4()
        r1 = await svc.renew(record_type="cost_est_results", record_id=rid, user_id=me)
        r2 = await svc.release(record_type="cost_est_results", record_id=rid, user_id=me)
        assert r1.degraded is True and r2.degraded is True
    finally:
        await svc.aclose()


async def test_degradation_banner_mentions_no_conflict_detection_for_unguarded_table():
    """**没接上 DB 兜底**的表 ⇒ 横幅须写「本次编辑无冲突检测」。

    ⚠️ **用户必须在无保护状态下知道这一点**（§⑤ 明写「不是可选的措辞优化」）。

    🔻 2026-10-20 D2 后：cost_est_results **已接上**（D2 把 guard 接进了它的
    保存路径）⇒ 它**不再**属于这一类。测试改用一张确实没有兜底的表。
    """
    from app.services.edit_guard import GUARDED_TABLES

    unguarded = next(
        (t for t in ("sim_tower_results", "util_results") if t not in GUARDED_TABLES),
        None,
    )
    assert unguarded is not None, "本仓的表要么已接上兜底，要么没有编辑路径"
    svc = EditLockService(DEAD_REDIS_URL)
    try:
        r = await svc.acquire(
            record_type=unguarded, record_id=_rid(), user_id=uuid.uuid4()
        )
        assert NO_CONFLICT_DETECTION_MESSAGE in (r.message or "")
    finally:
        await svc.aclose()


async def test_degradation_banner_omits_the_warning_for_a_guarded_table():
    """已接上 DB 兜底的表 ⇒ 横幅**不**写「无冲突检测」（否则是假话）。"""
    from app.services.edit_guard import GUARDED_TABLES

    guarded = "cost_est_results"
    assert guarded in GUARDED_TABLES, "D2 接线后 cost_est 必须在 GUARDED_TABLES 里"
    svc = EditLockService(DEAD_REDIS_URL)
    try:
        r = await svc.acquire(
            record_type=guarded, record_id=_rid(), user_id=uuid.uuid4()
        )
        assert DEGRADED_MESSAGE in (r.message or "")
        assert NO_CONFLICT_DETECTION_MESSAGE not in (r.message or "")
    finally:
        await svc.aclose()


async def test_banner_clause_follows_the_guarded_table_set():
    """横幅的「无冲突检测」从句**只**由 GUARDED_TABLES 决定（机制可测）。

    「已接上 DB 兜底」= D2 的 guard **真的接在该表的保存路径上**，不是
    「该表有 record_hash 列」（§⑤ 的横幅是给用户的事实陈述，不是能力表）。
    """
    from app.services.edit_guard import GUARDED_TABLES

    svc = EditLockService(DEAD_REDIS_URL)
    try:
        guarded = next(iter(sorted(GUARDED_TABLES)), None)
        unguarded = "sim_tower_results"  # 无 record_hash 的表
        r_guarded = await svc.acquire(
            record_type=guarded or unguarded, record_id=_rid(), user_id=uuid.uuid4()
        )
        r_unguarded = await svc.acquire(
            record_type=unguarded, record_id=_rid(), user_id=uuid.uuid4()
        )
        if guarded is None:
            # D1 阶段：GUARDED_TABLES 为空 ⇒ 还没有任何表接上 DB 兜底
            assert NO_CONFLICT_DETECTION_MESSAGE in (r_guarded.message or "")
        else:
            assert NO_CONFLICT_DETECTION_MESSAGE not in (r_guarded.message or "")
        assert NO_CONFLICT_DETECTION_MESSAGE in (r_unguarded.message or "")
    finally:
        await svc.aclose()


# ---------------------------------------------------------------------------
# ⑥ 锁判定不查库
# ---------------------------------------------------------------------------


async def test_acquire_does_not_consult_database():
    """锁是 UX 层 ⇒ **判定不查库**（§① 的两层锁前提）。

    守卫是**结构性**的：`EditLockService` 根本没有 session 参数，
    也不 import 任何 ORM / db 模块 ⇒ 「忘了查库」在类型层不可能发生。
    """
    import app.services.edit_lock as mod

    sig = inspect.signature(EditLockService.acquire)
    assert "db" not in sig.parameters
    assert "session" not in sig.parameters

    src = inspect.getsource(mod)
    for forbidden in ("app.db.", "app.models", "AsyncSession", "select("):
        assert forbidden not in src, f"编辑锁模块不得依赖数据库：{forbidden}"
