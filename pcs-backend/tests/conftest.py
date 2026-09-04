"""Sprint 1 + P2 共享测试 fixtures。

合并以下两组 fixture：

- **Task 1.2（最小 Sprint 1 集）**：`db_engine` / `db_session` / `client` /
  `user_id` / `owner_id` / `project_id` / `_avoid_real_db_probe`。
- **Task 2.7.1（P2 共享集）**：`db` 别名 / `actor` / `make_asset` 工厂 /
  `sample_draft_asset` 等样本资产 / `sample_sequence` / `sample_*_token`。

设计要点：

- `db` 别名指向 `db_session`，沿用 in-memory SQLite，避免影响现有 Sprint 1 测试。
- `make_asset` 返回单一 `ConfigAsset`（不是 bundle），新测试按需查询关联 version。
- `ConfigAsset.current_version` 是 `String(50)` 列（P1 SUP-001 §2.1 锁定），
  非 FK 关系，不能 `asset.current_version_id`；写入 `version_code` 字符串。
- `ConfigVersion` 没有 `formula_version` 列（与 brief 不同），不传该字段。
- Token fixture 用 `create_access_token`（P1 已实现）替代 brief 的 `make_token`
  （`app.auth.ldap_mock` 在代码库中不存在）。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import api_router
from app.core.security import create_access_token
from app.db.base import Base as SA_Base
from app.db.session import get_db
from app.models.config_domain import (
    ConfigAsset,
    ConfigVersion,
    DocNoSequence,
)
from app.models.enums import ConfigStatus

# ---------------------------------------------------------------------------
# SQLite JSONB / INET / Uuid 兼容垫片（Sprint 1 沿用）
# ---------------------------------------------------------------------------

SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON  # type: ignore[attr-defined]


def _visit_text_nolen(self, type_, **kw):  # noqa: ANN001, ANN201
    return "TEXT"


SQLiteTypeCompiler.visit_INET = _visit_text_nolen  # type: ignore[attr-defined]
SQLiteTypeCompiler.visit_UUID = _visit_text_nolen  # type: ignore[attr-defined]
try:
    from sqlalchemy import Uuid as SAUuid
    from sqlalchemy.dialects.postgresql import INET, JSONB

    JSONB.__visit_name__ = "JSON"  # type: ignore[attr-defined]
    INET.__visit_name__ = "VARCHAR"  # type: ignore[attr-defined]
    SAUuid.__visit_name__ = "VARCHAR"  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Task 1.2 fixtures（基础 Sprint 1 集）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """in-memory SQLite 异步引擎；测试隔离。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SA_Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        # Sprint 3: 关闭 flush 后 expire，避免 sync lazy-load 在 async 上下文触发 MissingGreenlet
        session.sync_session.expire_on_flush = False
        yield session


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def owner_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def project_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    """注入 in-memory session 的 httpx async client。"""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    # 建一个最小 app 避免 lifespan 触发真实 DB probe
    from fastapi import FastAPI

    from app.core.errors import install_exception_handlers

    app = FastAPI(title="PCS Test")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _avoid_real_db_probe(monkeypatch):
    """patch 同步 health check 为 True，避免 lifespan 触发真实连接。"""
    import app.db.session as db_session

    async def fake_async() -> bool:
        return True

    monkeypatch.setattr(db_session, "check_database", lambda: True, raising=True)
    monkeypatch.setattr(db_session, "check_database_async", fake_async, raising=True)
    yield


# ---------------------------------------------------------------------------
# Task 2.7.1 fixtures（P2 共享集）
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(db_session) -> AsyncIterator[AsyncSession]:
    """`db_session` 的 brief 命名别名。新 P2 测试统一引用此名。"""
    yield db_session


@pytest.fixture
def actor() -> uuid.UUID:
    """默认测试 actor UUID。"""
    return uuid.uuid4()


@pytest.fixture
def pc_actor() -> uuid.UUID:
    """PROCESS_CONTROLLER 角色 UUID。"""
    return uuid.uuid4()


@pytest.fixture
def designer_actor() -> uuid.UUID:
    """DESIGNER 角色 UUID。"""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def make_asset(db):
    """资产工厂：创建 ConfigAsset + v1 ConfigVersion 并 link。

    返回单一 ``ConfigAsset``；如需 version 对象，请按 ``asset_id`` 查询：

        asset = await make_asset()
        version = (await db.execute(
            select(ConfigVersion).where(ConfigVersion.asset_id == asset.asset_id)
        )).scalar_one()

    说明（与 brief 不同的两处）：

    - ``asset.current_version`` 是 ``String(50)`` 列，非 FK 关系
      （P1 SUP-001 §2.1 锁定），写入 ``version_code`` 字符串。
    - ``ConfigVersion`` 没有 ``formula_version`` 列，因此不传。
    """

    async def _make(
        *,
        status: str = ConfigStatus.DRAFT.value,
        category: str = "CATEGORY_2",
        name: str | None = None,
    ) -> ConfigAsset:
        asset = ConfigAsset(
            category=category,
            name=name or f"asset-{uuid.uuid4()}",
            current_version="v1",
            status=status,
        )
        db.add(asset)
        await db.flush()
        version = ConfigVersion(
            asset_id=asset.asset_id,
            version_code="v1",
            content_json={},
            status=status,
        )
        db.add(version)
        await db.flush()
        # 链接 via string column（schema 真实结构，非 FK）
        asset.current_version = version.version_code
        await db.flush()
        return asset

    return _make


async def _latest_version(db: AsyncSession, asset_id: uuid.UUID) -> ConfigVersion:
    """返回 asset 的最新 ConfigVersion（按 version_code 字典序）。"""
    result = await db.execute(
        select(ConfigVersion)
        .where(ConfigVersion.asset_id == asset_id)
        .order_by(ConfigVersion.version_code.desc())
    )
    return result.scalars().first()


@pytest_asyncio.fixture
async def sample_draft_asset(db, make_asset) -> ConfigAsset:
    return await make_asset(status=ConfigStatus.DRAFT.value)


@pytest_asyncio.fixture
async def sample_pending_asset(db, make_asset) -> ConfigAsset:
    return await make_asset(status=ConfigStatus.PENDING.value)


@pytest_asyncio.fixture
async def sample_pending_asset_c3(db, make_asset) -> ConfigAsset:
    return await make_asset(status=ConfigStatus.PENDING.value, category="CATEGORY_3")


@pytest_asyncio.fixture
async def sample_approved_formula_asset(db, make_asset) -> ConfigAsset:
    """公式资产 APPROVED + unit_tests 全通过。"""
    asset = await make_asset(status=ConfigStatus.APPROVED.value, category="CATEGORY_2")
    version = await _latest_version(db, asset.asset_id)
    version.content_json = {
        "expression": "a + b",
        "parameters_json": {"parameters": [{"name": "a"}, {"name": "b"}]},
        "unit_tests_json": {
            "unit_tests": [
                {"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01}
            ]
        },
    }
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def sample_approved_formula_with_preconditions(db, make_asset) -> ConfigAsset:
    """公式资产 APPROVED + preconditions 通过 + unit_tests 通过（TODO-031）。"""
    asset = await make_asset(status=ConfigStatus.APPROVED.value, category="CATEGORY_2")
    version = await _latest_version(db, asset.asset_id)
    version.content_json = {
        "expression": "a + b",
        "parameters_json": {
            "parameters": [{"name": "a", "default": 1.0}, {"name": "b", "default": 2.0}]
        },
        "unit_tests_json": {
            "unit_tests": [
                {"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01}
            ]
        },
        "preconditions": [
            {"id": "PC-001", "target": "params.a", "expression": "value > 0"}
        ],
    }
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def sample_approved_formula_failing_precondition(db, make_asset) -> ConfigAsset:
    """公式资产 APPROVED + unit_tests 通过但 precondition 违规（TODO-031）。"""
    asset = await make_asset(status=ConfigStatus.APPROVED.value, category="CATEGORY_2")
    version = await _latest_version(db, asset.asset_id)
    version.content_json = {
        "expression": "a + b",
        "parameters_json": {
            "parameters": [{"name": "a", "default": 1.0}, {"name": "b", "default": 2.0}]
        },
        "unit_tests_json": {
            "unit_tests": [
                {"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01}
            ]
        },
        "preconditions": [
            {"id": "PC-001", "target": "params.a", "expression": "value > 100"}
        ],
    }
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def sample_approved_formula_with_failing_test(db, make_asset) -> ConfigAsset:
    """公式资产 APPROVED + unit_tests 含一条失败。"""
    asset = await make_asset(status=ConfigStatus.APPROVED.value, category="CATEGORY_2")
    version = await _latest_version(db, asset.asset_id)
    version.content_json = {
        "expression": "a + b",
        "parameters_json": {"parameters": [{"name": "a"}, {"name": "b"}]},
        "unit_tests_json": {
            "unit_tests": [
                {"params": {"a": 1, "b": 2}, "expected": 3, "tolerance": 0.01},  # pass
                {"params": {"a": 2, "b": 2}, "expected": 999, "tolerance": 0.01},  # fail
            ]
        },
    }
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def sample_published_asset(db, make_asset) -> ConfigAsset:
    return await make_asset(status=ConfigStatus.PUBLISHED.value)


@pytest_asyncio.fixture
async def sample_two_version_asset(db, make_asset) -> ConfigAsset:
    """同一资产下两个 PUBLISHED 版本。"""
    asset = await make_asset(status=ConfigStatus.PUBLISHED.value)
    v2 = ConfigVersion(
        asset_id=asset.asset_id,
        version_code="v2",
        content_json={"new_field": 1},
        status=ConfigStatus.PUBLISHED.value,
    )
    db.add(v2)
    await db.flush()
    return asset


@pytest_asyncio.fixture
async def sample_sequence(db) -> DocNoSequence:
    """DocNoSequence 样本（NumberingService 测试用）。"""
    seq = DocNoSequence(
        project_id=uuid.uuid4(),
        template_id=uuid.uuid4(),
        scope_key="scope_A",
        current_value=0,
    )
    db.add(seq)
    await db.flush()
    return seq


@pytest.fixture
def sample_user_token() -> str:
    """默认 USER token（DESIGNER 角色；P1 用 mock_auth 解码）。"""
    return create_access_token(subject="test-user", role="DESIGNER")


@pytest.fixture
def sample_pc_token() -> str:
    """PROCESS_CONTROLLER 角色 token。"""
    return create_access_token(subject="test-pc", role="PROCESS_CONTROLLER")


@pytest.fixture
def sample_designer_token() -> str:
    """DESIGNER 角色 token。"""
    return create_access_token(subject="test-designer", role="DESIGNER")