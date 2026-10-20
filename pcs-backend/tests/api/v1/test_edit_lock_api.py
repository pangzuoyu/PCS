"""编辑锁 API 测试 —— P9A-4 D1（ADR-0048 §①⑤ · SPEC §6.21）。

端点：

- ``POST /api/v1/locks/{record_type}/{record_id}/acquire``
- ``POST /api/v1/locks/{record_type}/{record_id}/renew``
- ``POST /api/v1/locks/{record_type}/{record_id}/release``

## 本文件只验「接线 + 契约」，不重复验锁语义

锁语义（TTL / 续期 / 归属）在 `tests/services/test_edit_lock.py` 里测了一遍
（真 Redis）。这里测的是：端点存在、状态码对、**409 带持锁人信息**、
降级横幅、审计留痕。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import select

from app.models.system import AuditLog
from app.services.edit_lock import (
    DEGRADED_MESSAGE,
    NO_CONFLICT_DETECTION_MESSAGE,
    EditLockService,
    get_edit_lock,
    set_edit_lock,
)

REDIS_URL = "redis://localhost:6379/9"
DEAD_REDIS_URL = "redis://127.0.0.1:6399/0"  # 无人监听


async def _redis_up() -> bool:
    r = aioredis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
    try:
        await r.ping()
    except Exception:  # noqa: BLE001
        return False
    finally:
        await r.aclose()
    return True


@pytest_asyncio.fixture
async def lock_service():
    """把进程级单例指向测试用的 Redis（DB 9），测完还原。"""
    if not await _redis_up():
        pytest.skip("真 Redis 未运行（docker compose up redis）")
    svc = EditLockService(REDIS_URL)
    set_edit_lock(svc)
    try:
        yield svc
    finally:
        set_edit_lock(None)
        await svc.aclose()


@pytest_asyncio.fixture
async def dead_lock_service():
    """Redis 不可用 ⇒ 降级放行（§⑤）。"""
    svc = EditLockService(DEAD_REDIS_URL)
    set_edit_lock(svc)
    try:
        yield svc
    finally:
        set_edit_lock(None)
        await svc.aclose()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# acquire
# ---------------------------------------------------------------------------


async def test_acquire_grants_the_lock(client, sample_user_token, lock_service):
    rid = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["success"] is True
    assert data["degraded"] is False
    assert data["record_type"] == "cost_est_results"
    assert data["record_id"] == rid
    assert data["holder"]["user_id"]


async def test_acquire_by_another_user_returns_409_with_holder_info(
    client, sample_user_token, sample_pc_token, lock_service
):
    """他人持锁 ⇒ **409 + 持锁人信息**（不是裸 409）。"""
    rid = str(uuid.uuid4())
    r1 = await client.post(
        f"/api/v1/locks/psychro_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r1.status_code == 200

    r2 = await client.post(
        f"/api/v1/locks/psychro_results/{rid}/acquire",
        headers=_auth(sample_pc_token),
    )
    assert r2.status_code == 409, f"got {r2.status_code}: {r2.text}"
    data = r2.json()
    assert data["success"] is False
    assert data["holder"]["user_id"] == r1.json()["holder"]["user_id"]
    assert data["holder"]["acquired_at"]


async def test_holder_info_carries_the_username(client, sample_user_token, lock_service):
    """持锁人信息带**显示名** ⇒ 前端不必再查一次用户（锁判定不查库）。"""
    rid = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200
    assert r.json()["holder"]["username"] == "test-user"


async def test_acquire_requires_authentication(client, lock_service):
    rid = str(uuid.uuid4())
    r = await client.post(f"/api/v1/locks/cost_est_results/{rid}/acquire")
    assert r.status_code in (401, 403), f"got {r.status_code}"


async def test_acquire_writes_an_audit_row(client, sample_user_token, lock_service, db_session):
    """ADR-0048 §①：锁的 acquire 写 audit_logs（DB 保留审计留痕）。"""
    rid = str(uuid.uuid4())
    await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "EDIT_LOCK_ACQUIRED")
        )
    ).scalars().all()
    assert rows, "acquire 未写审计"
    assert rows[-1].resource_type == "cost_est_results"
    assert rows[-1].resource_id == rid


# ---------------------------------------------------------------------------
# renew / release
# ---------------------------------------------------------------------------


async def test_renew_by_the_holder_succeeds(client, sample_user_token, lock_service):
    rid = str(uuid.uuid4())
    await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/renew",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["success"] is True


async def test_renew_by_another_user_returns_409(
    client, sample_user_token, sample_pc_token, lock_service
):
    """他人的心跳不得延长我的锁 ⇒ 409。"""
    rid = str(uuid.uuid4())
    await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/renew",
        headers=_auth(sample_pc_token),
    )
    assert r.status_code == 409, f"got {r.status_code}: {r.text}"


async def test_release_by_another_user_returns_409(
    client, sample_user_token, sample_pc_token, lock_service
):
    """非持有者 release ⇒ 409（且**不得**动别人的锁）。"""
    rid = str(uuid.uuid4())
    await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/release",
        headers=_auth(sample_pc_token),
    )
    assert r.status_code == 409, f"got {r.status_code}: {r.text}"

    # 我的锁还在
    r2 = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/renew",
        headers=_auth(sample_user_token),
    )
    assert r2.status_code == 200 and r2.json()["success"] is True


async def test_release_by_the_holder_succeeds(client, sample_user_token, lock_service):
    rid = str(uuid.uuid4())
    await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/release",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# 降级（§⑤）
# ---------------------------------------------------------------------------


async def test_redis_down_degrades_with_a_banner_not_503(
    client, sample_user_token, dead_lock_service
):
    """Redis 不可用 ⇒ **降级放行**（200 + degraded + 横幅），**不是 503**。"""
    rid = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["degraded"] is True
    assert data["success"] is True
    assert DEGRADED_MESSAGE in data["message"]
    assert NO_CONFLICT_DETECTION_MESSAGE in data["message"]


async def test_degraded_acquire_still_works_when_the_audit_fails(
    client, sample_user_token, dead_lock_service, monkeypatch
):
    """审计写失败**不得**让锁请求失败（锁已经拿到了）。"""
    from app.services.audit_service import AuditService

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("DB 挂了")

    monkeypatch.setattr(AuditService, "write", _boom)
    rid = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/locks/cost_est_results/{rid}/acquire",
        headers=_auth(sample_user_token),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    assert r.json()["success"] is True


async def test_lock_service_singleton_is_shared(client):
    """进程级单例（Redis 连接是进程级资源）。"""
    assert get_edit_lock() is get_edit_lock()
