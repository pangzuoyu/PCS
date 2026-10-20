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

import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.sqlite.base import SQLiteDDLCompiler, SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.schema import ColumnDefault

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

# SQLite 不支持 PostgreSQL NOW() / gen_random_uuid() 函数；
# DDL 重写为 SQLite 等价表达（CURRENT_TIMESTAMP / 应用层 default）。
_orig_create_column = SQLiteDDLCompiler.visit_create_column


def _visit_create_column(self, *args, **kwargs):  # noqa: ANN001, ANN202
    rendered = _orig_create_column(self, *args, **kwargs)
    return rendered.replace("NOW()", "CURRENT_TIMESTAMP")


SQLiteDDLCompiler.visit_create_column = _visit_create_column  # type: ignore[attr-defined]


# CHECK 里的 PostgreSQL 专有 `interval 'N second'` 是**类型字面量**而非函数调用，
# SQLite 的分词器在 CREATE TABLE 阶段就报 syntax error —— 注册 UDF 也救不了
# （函数解析发生在建表之前）。按**约束名**逐条给出 SQLite 等价式。
#
# 两侧都套 julianday 是必需的：SQLite 里 DATETIME 存成 TEXT，
# 而 julianday() 返回 REAL，而 SQLite 排序规则把**所有数值排在所有文本之前**，
# 于是 `TEXT <= REAL` 恒为假 —— 只包右侧会让约束把每一行都拒掉。
_SQLITE_CHECK_OVERRIDES = {
    "future_dated_forbidden_chk": (
        "julianday(effective_from) <= julianday(created_at) + 1.0/86400"
    ),
}
_orig_visit_check_constraint = SQLiteDDLCompiler.visit_check_constraint


def _visit_check_constraint(self, constraint, **kw):  # noqa: ANN001, ANN201
    override = _SQLITE_CHECK_OVERRIDES.get(constraint.name)
    if override is None:
        return _orig_visit_check_constraint(self, constraint, **kw)
    return f"CONSTRAINT {constraint.name} CHECK ({override})"


SQLiteDDLCompiler.visit_check_constraint = _visit_check_constraint  # type: ignore[attr-defined]


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
    import os
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=bool(os.environ.get("SQL_ECHO")),
    )

    # SQLite 不支持 PostgreSQL gen_random_uuid() 函数；
    # 通过 connect 钩子注册 SQLite 自定义函数（每次 INSERT 触发 DEFAULT 时调用）。
    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_pg_functions(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.create_function(
            "gen_random_uuid", 0, lambda: str(uuid.uuid4())
        )

    # SQLite 不支持 PostgreSQL gen_random_uuid() server_default；
    # 清掉 server_default 并附加 Python-side ColumnDefault（绕过 RETURNING 问题）。
    for _table in SA_Base.metadata.tables.values():
        for _col in _table.columns:
            sd = _col.server_default
            if sd is not None and "gen_random_uuid" in str(sd.arg):
                _col.server_default = None
                _col.default = ColumnDefault(uuid.uuid4)

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
def user_id(request) -> uuid.UUID:
    """user_id fixture.

    若 test 同时请求 project_id + db_session, 自动 grant UserProject DESIGNER.
    """
    return uuid.uuid4()


@pytest.fixture
def owner_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest_asyncio.fixture
async def project_id(db_session: AsyncSession, user_id) -> uuid.UUID:
    """project_id fixture (BLOCKER-3 自动 grant, async 版本).

    当 test 同时使用 user_id + project_id + db_session 时, 自动 grant
    UserProject DESIGNER 角色. 让既有测试透明通过 BLOCKER-3 守卫.

    注: 必须 async fixture (sync fixture 不能在 async 上下文用 sync_engine grant).
    """
    from app.services.user_project_service import UserProjectService

    pid = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id,
        project_id=pid,
        role_in_project="DESIGNER",
    )
    return pid


@pytest.fixture
def workspace_id() -> uuid.UUID:
    """HIGH P1-2 — 测试统一 workspace context 注入点。"""
    return uuid.uuid4()


# 注: granted_user_project fixture (async) 已废弃 — 改用 project_id fixture
# 同步 grant 实现 (兼容 SQLite in-memory 测试). 上面的 user_id/project_id fixtures
# 协同工作, 测试只需声明 user_id + project_id 即自动 grant."


@pytest_asyncio.fixture
async def workspace(db_session, workspace_id, project_id):
    """HIGH P1-2 — 异步 fixture 中建一个 FORMAL Workspace 记录，workspace_id 可预测。

    用法：``async def test_x(client, workspace): ...`` —— ``get_workspace``
    依赖 ``workspace_id`` query/path/header 参数时，httpx ``client.get(
    f"/.../workspaces/{workspace.workspace_id}/...")`` 即可命中已建记录。

    ⚠️ 2026-10-20 修复：原实现传 ``workspace_name=``，而 ``Workspace`` 的列叫
    ``name`` ⇒ **任何用到本 fixture 的测试都会 TypeError**。之所以一直没被发现：
    没有测试用它（fixture 写于 P1-2，之后的测试各自造 workspace）。
    同时补 ``project_id`` —— ``check_project_access_or_404`` 依赖它，
    否则 workspace 侧的项目归属恒为 None，项目守卫会被静默跳过。
    """
    from app.models.enums import WorkspaceType
    from app.models.project import Workspace

    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type=WorkspaceType.FORMAL.value,
        name="Test Workspace",
        project_id=project_id,
        status="ACTIVE",
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return ws


@pytest_asyncio.fixture
async def client(db_engine, monkeypatch) -> AsyncIterator[AsyncClient]:
    """注入 in-memory session 的 httpx async client.

    BLOCKER-3 测试 override: 自动 bypass UserProject guard
    (mock check_user_project_access → True). 测试不验证 ACL 行为
    (那是 test_user_project_service.py 的职责). 仅 client fixture
    影响 — service-only 测试不受影响.
    """
    from app.services import user_project_service

    async def _mock_check(*_args, **_kwargs):
        return True

    monkeypatch.setattr(
        user_project_service.UserProjectService,
        "check_user_project_access",
        _mock_check,
    )

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


@pytest.fixture(autouse=True)
def _clear_rbac_rate_limits():
    """F-P3-001 #5: 每测试清空 RBAC 拒绝限流窗口（模块级全局, 防跨测试 429 污染）。"""
    from app.services._sliding_window_rate_limit import clear_all_rate_limits

    clear_all_rate_limits()
    yield
    clear_all_rate_limits()


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
async def make_user(db):
    """用户工厂：`await make_user("zhang", ["REVIEWER"])` → user_id。

    P9A C1b 起需要**真的落一行 users**：通知的 `recipient_id` 有指向
    `users.user_id` 的外键，而收件人解析（`notification_recipients`）要读
    `users.roles` 与 `users.status`。
    """

    async def _make(username: str, roles: list[str], status: str = "ACTIVE") -> uuid.UUID:
        from app.models.project import User

        u = User(username=username, display_name=username, roles=roles, status=status)
        db.add(u)
        await db.flush()
        return u.user_id

    return _make


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

# === P8 报表字体 ============================================================
#
# 字体**不入库**（用户 2026-10-09 裁决）：仓库里没有 CJK 字体文件，产物由
# `scripts/build_report_font.py` 从 OFL 可变字体现场派生。
#
# 这里**自动派生而不是 skip** —— 「本机没装字体所以跳过 PDF 测试」正是这个
# 项目最熟悉的假绿（bug-143/145/149/150/152）：绿灯测的不是出问题那层。
# 派生不出来就该红，因为真跑起来一样会红。
@pytest.fixture(scope="session")
def report_font_path() -> Path:
    """确保 REPORT_FONT_DIR 里有可用的中文字体，返回其路径。"""
    from app.core.config import get_settings

    out = Path(get_settings().report_font_dir) / "NotoSansSC-Regular.ttf"
    if not out.exists():
        import subprocess

        r = subprocess.run(
            [sys.executable, "scripts/build_report_font.py", "--out", str(out)],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not out.exists():
            pytest.fail(
                "中文字体派生失败，PDF 渲染测试无法进行（不 skip —— skip 就是假绿）：\n"
                f"{r.stdout}\n{r.stderr}"
            )
    return out


# === P8 报表字体注册表（**全局**状态，必须全仓唯一的清理点）===============
#
# `pdfmetrics` 是 reportlab 的**全局**注册表，任何渲染过 PDF 的测试都会往里
# 写字体。清理逻辑若放在单个测试模块里，就只能看见「自己注册过的」——
# 别的模块（Golden 测试）先注册了同名字体，本模块的快照里它已经存在，
# 于是不会被清掉。后果：`_missing_glyphs` 读到的是上一个测试留下的字体，
# 字形覆盖判定跟着错（实测会红两条字体守卫测试）。
#
# 故放 conftest 且 autouse：每个测试都从干净的注册表开始。
@pytest.fixture(autouse=True)
def _reset_report_font_registry(request):
    """快照-还原 reportlab 的字体注册表 + 本仓的已注册缓存。

    两个状态都要清：只清 `_REGISTERED` 会让 `pdfmetrics` 里的旧字体
    命中缓存、`getFont` **根本不重新校验字形**；只清 `pdfmetrics` 则
    本仓缓存会让 `_register_font` 直接短路返回。
    """
    if "report" not in str(request.node.fspath).replace("\\", "/"):
        yield                      # 只对报表相关测试生效，避免拖慢全仓
        return
    from app.services.report import renderer_pdf

    before = set(renderer_pdf.pdfmetrics._fonts)
    renderer_pdf._REGISTERED.clear()
    yield
    for name in set(renderer_pdf.pdfmetrics._fonts) - before:
        renderer_pdf._unregister_font(name)
    renderer_pdf._REGISTERED.clear()


def pytest_addoption(parser):
    """Golden 基线重生成开关。

    ⚠️ **必须定义在 rootdir 的 conftest**，不能放在 `test_golden.py` 里 ——
    pytest 在收集开始前解析命令行选项，那时测试模块尚未 import，
    模块内的 `pytest_addoption` 不会被注册（报
    `ValueError: no option named '--update-golden'`）。

    用法：改了报表字段后
        pytest tests/services/report/test_golden.py --update-golden
    并**逐条看 diff** —— 不看就重新生成等于把回归固化成基线。
    """
    parser.addoption(
        "--update-golden", action="store_true", default=False,
        help="重新生成 Golden 基线。改过报表字段后用；务必逐条看 diff")
