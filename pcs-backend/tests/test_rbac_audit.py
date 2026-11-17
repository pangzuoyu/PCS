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


async def test_write_rbac_audit_row_persists_via_own_session(
        db_engine, db, monkeypatch):
    """`_write_rbac_audit_row` 自己开 session 写入 audit_logs 并提交。

    - monkeypatch get_async_session_factory → 测试 engine factory
    - 清 PYTEST_CURRENT_TEST (writer 在 pytest 下默认跳过防写真库)

    ⚠️ 原名 `..._real_db` 有误导（2026-10-18 StaticPool 审计改）：跑的仍是
    `:memory:` SQLite，不是真库。且「writer 与断言用的 `db` 共享同一条
    StaticPool 连接」意味着本条**察觉不到 writer 忘了 commit** —— 断言
    在未提交状态下也读得到。它今天成立是因为 `errors.py:58` 确有
    `await session.commit()`；若要钉死 commit 行为，需按
    `test_cron_reclaim_commits_...` 的样板改用文件库（未做，登记在
    TODOS.md 的 StaticPool 审计条目里）。
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


# ---------------------------------------------------------------------------
# pytest 下的「写不写」判据（P10-B 评审 #10 · P2）
#
# ⚠️ 早退的理由是「防测试写真实 DB」⇒ ⇒ 而车道的库**已经是隔离 schema**
# ⇒ ⇒ 早退在车道里**没有理由** ⇒ ⇒ 「越权 ⇒ 留痕」在车道里必须是**真跑**。
#
# ⚠️ **判据不能是环境变量**（`PCS_E2E_LANE` 谁都能设）⇒ ⇒ 判据是
# **真实连接**（`current_database()` + `current_schema()`）。
# ---------------------------------------------------------------------------


class _StubResult:
    """`session.execute(...).scalar_one()` 的假结果。"""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _StubSession:
    """只回答 `current_database()` / `current_schema()` 的假 session。"""

    def __init__(self, db_name: str, schema: str):
        self._db_name = db_name
        self._schema = schema
        self.committed = False

    async def execute(self, statement):
        sql = str(statement)
        if "current_database()" in sql:
            return _StubResult(self._db_name)
        if "current_schema()" in sql:
            return _StubResult(self._schema)
        raise AssertionError(f"意料之外的 SQL：{sql}")

    async def commit(self):
        self.committed = True


class _StubBind:
    def __init__(self, url: str):
        self.url = url


class _StubFactory:
    """假 session factory（`kw['bind'].url` = 它**真正会连**的库）。"""

    def __init__(self, session: _StubSession, url: str):
        self._session = session
        self.kw = {"bind": _StubBind(url)}
        self.opened = 0

    def __call__(self) -> "_StubFactory":
        return self

    async def __aenter__(self) -> _StubSession:
        self.opened += 1
        return self._session

    async def __aexit__(self, *exc) -> bool:
        return False


class _StubAuditService:
    """记录 `write()` 调用（不真写库）。"""

    calls: list[dict] = []

    def __init__(self, session):
        self.session = session

    async def write(self, **kwargs):
        _StubAuditService.calls.append(kwargs)
        return object()


@pytest.fixture
def stub_audit_target(monkeypatch):
    """装好「审计目标」的假上下文 ⇒ 返回装填器（返回假 factory）。"""
    import app.db.session as db_session_mod
    import app.services.audit_service as audit_service_mod

    _StubAuditService.calls = []

    def _install(*, url: str, db_name: str, schema: str) -> _StubFactory:
        factory = _StubFactory(_StubSession(db_name, schema), url)
        monkeypatch.setattr(
            db_session_mod, "get_async_session_factory", lambda: factory
        )
        monkeypatch.setattr(audit_service_mod, "AuditService", _StubAuditService)
        return factory

    return _install


async def test_under_pytest_a_non_lane_database_is_not_even_connected(
    monkeypatch, stub_audit_target
):
    """pytest 下、目标库**不是**车道库 ⇒ 不写审计行，且**连都不连**。

    ⚠️ 「连都不连」是关键 —— 单测车道的全局 factory 指**开发库** ⇒ ⇒
    连上去问「我在哪个库」就等于**单测车道去碰开发库**。
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "unit (call)")
    factory = stub_audit_target(
        url="postgresql+psycopg://pcs:***@localhost:5432/pcs",
        db_name="pcs",
        schema="public",
    )

    await errors_mod._write_rbac_audit_row(user_id=None, detail={"path": "/x"})

    assert _StubAuditService.calls == [], "非白名单库竟然写了审计行"
    assert factory.opened == 0, "非白名单库竟然被连上了 ⇒ 单测车道会去碰开发库"


async def test_under_pytest_the_lane_database_but_public_schema_is_not_written(
    monkeypatch, stub_audit_target
):
    """pytest 下、白名单库但 **public schema** ⇒ 不写（共享 schema 不能被测试写）。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "unit (call)")
    factory = stub_audit_target(
        url="postgresql+asyncpg://pcs:***@localhost:5433/pcs_pgtest",
        db_name="pcs_pgtest",
        schema="public",
    )

    await errors_mod._write_rbac_audit_row(user_id=None, detail={"path": "/x"})

    assert _StubAuditService.calls == [], "public schema 竟然被写了审计行"
    assert factory.opened == 1, "白名单库应当被连上再判定（真判据 = 真实连接）"


async def test_under_pytest_an_isolated_lane_context_writes_the_audit_row(
    monkeypatch, stub_audit_target
):
    """pytest 下、**隔离 schema** ⇒ 写审计行（P10-B 评审 #10 的落点）。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "unit (call)")
    stub_audit_target(
        url="postgresql+asyncpg://pcs:***@localhost:5433/pcs_pgtest",
        db_name="pcs_pgtest",
        schema="e2e_ab12cd34",
    )

    detail = {"path": "/api/v1/audit-logs", "status": 403}
    await errors_mod._write_rbac_audit_row(user_id=uuid.uuid4(), detail=detail)

    assert len(_StubAuditService.calls) == 1, "隔离 schema 里竟然没写审计行"
    call = _StubAuditService.calls[0]
    assert call["action"] == "RBAC_DENIED"
    assert call["resource_type"] == "AUTHZ"
    assert call["detail"] == detail


async def test_under_pytest_a_url_that_lies_about_the_lane_is_rejected(
    monkeypatch, stub_audit_target
):
    """URL 说「车道库」、**真连**却是别的库 ⇒ 不写（fail-closed）。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "unit (call)")
    stub_audit_target(
        url="postgresql+asyncpg://pcs:***@localhost:5433/pcs_pgtest",
        db_name="pcs",  # ⚠️ URL 说车道库，真连接却不是
        schema="e2e_ab12cd34",
    )

    await errors_mod._write_rbac_audit_row(user_id=None, detail={"path": "/x"})

    assert _StubAuditService.calls == [], "真连接不在白名单却写了审计行"