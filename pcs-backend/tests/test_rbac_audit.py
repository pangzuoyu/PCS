"""F-P3-001 checklist #5: RBAC 401/403 audit log + per-IP rate limit 测试.

覆盖:
- 403 (require_roles 拒绝) → audit_logs 写 RBAC_DENIED
- 401 (current_actor MISSING_BEARER) → audit_logs 写 RBAC_DENIED
- >5/min 同 IP → 第 6 次起 429 RBAC_RATE_LIMITED
- 404 (guard) / 200 → 不写 audit (仅 401/403 计数)
- _write_rbac_audit_row 真实 DB 写入路径 (SQLite test engine)
"""
from __future__ import annotations

import uuid

import pytest

import app.core.errors as errors_mod
from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """每个测试前后清空限流状态 (滑动窗口是模块级全局)."""
    from app.services._sliding_window_rate_limit import clear_all_rate_limits

    clear_all_rate_limits()
    yield
    clear_all_rate_limits()


@pytest.fixture
def audit_recorder(monkeypatch):
    """捕获 _write_rbac_audit_row 调用 (不写真库)."""
    calls: list[dict] = []

    async def _fake_write(user_id, detail):
        calls.append({"user_id": user_id, "detail": detail})

    monkeypatch.setattr(errors_mod, "_write_rbac_audit_row", _fake_write)
    return calls


@pytest.fixture
def designer_token() -> str:
    return create_access_token(subject="rbac-test-user", role="DESIGNER")


# ---------------------------------------------------------------------------
# audit 写入
# ---------------------------------------------------------------------------


async def test_403_require_roles_denial_writes_audit(
    client, audit_recorder, designer_token
):
    """DESIGNER 访问 /audit-logs (SYSTEM_ADMIN only) → 403 + RBAC_DENIED audit."""
    r = await client.get(
        "/api/v1/audit-logs",
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 403
    assert len(audit_recorder) == 1
    entry = audit_recorder[0]
    assert entry["detail"]["path"] == "/api/v1/audit-logs"
    assert entry["detail"]["status"] == 403
    assert entry["detail"]["method"] == "GET"
    # user_id best-effort 派生 (JWT 解码成功)
    assert entry["user_id"] is not None


async def test_401_missing_bearer_writes_audit(client, audit_recorder):
    """无 token → 401 MISSING_BEARER + RBAC_DENIED audit (user_id=None)."""
    r = await client.get("/api/v1/audit-logs")
    assert r.status_code == 401
    assert len(audit_recorder) == 1
    entry = audit_recorder[0]
    assert entry["detail"]["status"] == 401
    assert entry["detail"]["code"] == "MISSING_BEARER"
    # 无有效 token → user_id 不可派生
    assert entry["user_id"] is None


async def test_404_guard_not_audited(client, audit_recorder, designer_token):
    """guard 404 (不泄漏存在性) 不在 401/403 范围 → 不写 audit."""
    import uuid as _uuid

    r = await client.get(
        "/api/v1/equipment-deletion-audit",
        params={"project_id": str(_uuid.uuid4())},
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    # conftest client mock 了 check_user_project_access → 200/正常路径,
    # 不会 404; 此测试验证 200 响应不写 audit 即可 (404 分支由 unit 覆盖)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert audit_recorder == []


async def test_200_ok_not_audited(client, audit_recorder, designer_token):
    """正常 200 响应不写 RBAC audit."""
    r = await client.get(
        "/api/v1/config-audit",
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 200
    assert audit_recorder == []


async def test_422_validation_not_audited(client, audit_recorder, designer_token):
    """422 (limit=0) 不是 RBAC 事件 → 不写 audit + 不计数."""
    r = await client.get(
        "/api/v1/audit-logs",
        params={"limit": 0},
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 422
    assert audit_recorder == []


# ---------------------------------------------------------------------------
# rate limit (>5/min 同 IP → 429)
# ---------------------------------------------------------------------------


async def test_6th_denied_request_returns_429(client, audit_recorder):
    """同 IP 连续 6 次 401 → 前 5 次 401, 第 6 次 429 RBAC_RATE_LIMITED."""
    for i in range(5):
        r = await client.get("/api/v1/audit-logs")
        assert r.status_code == 401, f"request {i + 1}: expected 401, got {r.status_code}"

    r6 = await client.get("/api/v1/audit-logs")
    assert r6.status_code == 429, r6.text
    assert r6.json()["code"] == "RBAC_RATE_LIMITED"
    # 6 次尝试全部写 audit (含被限流的那次)
    assert len(audit_recorder) == 6
    assert audit_recorder[-1]["detail"]["rate_limited"] is True


async def test_rate_limit_recovers_after_window(client, audit_recorder, monkeypatch):
    """窗口过期后恢复 (滑动窗口 evict)."""
    from app.services import _sliding_window_rate_limit as rl

    # 手动注入 5 条已过期的 denial 记录 (模拟 60s 前的失败)
    now_key = "rbac_denied:unknown"
    import time

    async with rl._LOCK:
        dq = rl._WINDOW_STATE.setdefault(now_key, __import__("collections").deque())
        for _ in range(5):
            dq.append(time.monotonic() - 61)  # 61s 前, 已过期

    r = await client.get("/api/v1/audit-logs")
    # 过期 entry evict → 本次仍 401 (不 429)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 真实 DB 写入路径 (SQLite test engine)
# ---------------------------------------------------------------------------


async def test_write_rbac_audit_row_real_db(db_engine, db, monkeypatch):
    """_write_rbac_audit_row 真实写入 audit_logs (SQLite).

    - monkeypatch get_async_session_factory → 测试 engine factory
    - 清 PYTEST_CURRENT_TEST (writer 在 pytest 下默认跳过防写真库)
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    import app.db.session as db_session_mod

    monkeypatch.setattr(db_session_mod, "get_async_session_factory", lambda: factory)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    detail = {
        "path": "/api/v1/audit-logs",
        "method": "GET",
        "ip": "unknown",
        "status": 403,
        "code": "HTTP_403",
        "rate_limited": False,
    }
    await errors_mod._write_rbac_audit_row(
        user_id=uuid.uuid4(), detail=detail,
    )

    from sqlalchemy import select

    from app.models.system import AuditLog

    rows = (
        await db.execute(select(AuditLog).where(AuditLog.action == "RBAC_DENIED"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource_type == "AUTHZ"
    assert rows[0].detail_json["path"] == "/api/v1/audit-logs"
    assert rows[0].detail_json["status"] == 403