"""E2E 车道（隔离 schema · 真 PG）的 fixture —— P10-B · T1。

## 这个车道是什么

**真 PG + 真 app + 真中间件链** ⇒ 场景走的是**生产同款**路径（守卫、审计、
trace 都真跑）⇒ 与单测车道（内存 SQLite + mock 守卫）互补。

## ⚠️ 三条必须守住的不变量

1. **隔离** —— E2E 的行**只**落在隔离 schema ⇒ **开发库 public schema 一个字节不动**。
   ⇒ 用 `options=-csearch_path=<schema>`（照
   `tests/api/v1/test_stream_batch_concurrency_pg.py` 的形状）。
2. **默认车道绝不碰 `e2e`** —— `pytest_collection_modifyitems` 闸门：
   没有 `PCS_E2E_LANE=1` ⇒ 全部 skip。
   ⇒ 为什么必须有：`pyproject.toml` 的 `addopts` 只有 `-m 'not visual'`
   ⇒ 仓里**没有任何**东西排除 `e2e` ⇒ 不加闸门，批末那句 `uv run pytest`
   会把 E2E 场景**跑到开发库 `pcs` 上** ⇒ 而症状是「跑得挺快、全绿」⇒ 没人发现。
3. **`e2e_client` 走真 app** —— `create_app()`（不是 `strict_client` 那套最小 app）
   ⇒ 真中间件链（审计 / trace / CORS）⇒ 场景验的是**生产同款**行为。

## ⚠️ 为什么这个目录是 `tests/e2e_flows/` 而不是 `tests/e2e/`

`tests/e2e/` **已被占用**（`test_sim_three_entry_consistency.py` · 12 条
`@pytest.mark.asyncio` · **无 skip**）⇒ 在那儿放新的 `conftest.py` ⇒
它的 autouse / skip 逻辑会**静默改掉**那 12 条既有用例的行为
⇒ ⇒ 换到兄弟目录 ⇒ 既有用例**一个字节都不动**。
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from app.core.db_guard import (
    assert_allowed_lane_database,
    db_name_from_url,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]

#: 全局角色的**白名单** —— 与 `app/api/v1/config.py::_ALLOWED_ROLES` 同款。
#:
#: ⚠️ 这里 copy 一份是为了**早失败**（非法角色 ⇒ 立刻报错，而不是发一个
#: 会被 403 的 token ⇒ 症状离病因很远）。
#: ⚠️ **漂移由测试钉住** ⇒ `test_role_headers_rejects_a_role_outside_the_allowlist`
#: 会把这份 copy 与**应用源码里那份**逐个比对 ⇒ 改一处不改两处 ⇒ 测试会红。
ALLOWED_ROLES = frozenset(
    {
        "DESIGNER",
        "PROCESS_CONTROLLER",
        "REVIEWER",
        "APPROVER",
        "SYSTEM_ADMIN",
        "VIEWER",
        "CHECKER",
    }
)

#: 车道标识 —— `scripts/pytest_e2e.sh` 导出 ⇒ 默认车道没有 ⇒ 闸门全跳。
LANE_ENV_VAR = "PCS_E2E_LANE"


# ---------------------------------------------------------------------------
# 闸门：默认车道必须跳过 `e2e`
# ---------------------------------------------------------------------------


def _skip_e2e_items_unless_in_lane(session, config, items) -> None:
    """没有 `PCS_E2E_LANE=1` ⇒ 给每个 `e2e` 用例打 skip 标记。

    ⚠️ **这是本批最危险的一条**：不加它，批末那句 `uv run pytest`
    会把 E2E 场景**跑到开发库 `pcs` 上**（建隔离 schema + 跑 alembic）
    ⇒ 而症状是「跑得挺快、全绿」⇒ **没人发现**。
    """
    if os.environ.get(LANE_ENV_VAR) == "1":
        return
    skip = pytest.mark.skip(reason="E2E 车道专属用例（默认车道跳过 · 须经 scripts/pytest_e2e.sh）")
    for item in items:
        if item.get_closest_marker("e2e") is not None:
            item.add_marker(skip)


def pytest_collection_modifyitems(session, config, items) -> None:
    _skip_e2e_items_unless_in_lane(session, config, items)


# ---------------------------------------------------------------------------
# URL 工具
# ---------------------------------------------------------------------------


def _lane_url() -> str:
    """车道导出的 PG URL（`scripts/pytest_pg.sh` 导出 `DATABASE_URL`）。"""
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgres"):
        raise RuntimeError(
            "不在 E2E 车道里（DATABASE_URL 不是 postgres URL）"
            "⇒ 须经 scripts/pytest_e2e.sh 跑（唯一入口）"
        )
    # ⚠️ **目标库白名单**（P10-B 评审 #8 · P1）：车道会**建 schema + 跑迁移 + 灌种子**
    # ⇒ ⇒ 指向开发库 `pcs` 就会**污染开发数据** ⇒ ⇒ 先按 URL 里的库名**快速拒**
    # （连都不连 ⇒ 不给误操作留窗口）⇒ 真判据（`current_database()`）在
    # `e2e_schema` fixture 里 —— 那才是「连上去的那个库」。
    assert_allowed_lane_database(
        db_name_from_url(url), purpose="E2E 车道（DATABASE_URL）"
    )
    return url


def _scoped_url(url: str, schema: str) -> str:
    """隔离 schema 的 URL = 原 URL **追加** `options=-csearch_path=<schema>`。

    ⚠️ `?` 还是 `&` 看原 URL 有没有 query（照
    `tests/api/v1/test_stream_batch_concurrency_pg.py` 的判据 ⇒ 抄错会建到 public）。
    """
    return url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"


def _async_url(url: str) -> str:
    """**异步**引擎的 URL = 换成 **asyncpg**（= 生产用的驱动）。

    ⚠️ **为什么必须换**（2026-11-16 · T7 实测）：车道的 `DATABASE_URL` 是
    `postgresql+psycopg://` ⇒ async 部分若也用 psycopg ⇒ ⇒ **驱动与生产
    不一致** ⇒ ⇒ **asyncpg 的类型严格性看不到** ⇒ ⇒ 例如
    `report_definitions.version` 是 **VARCHAR** 而种子塞了 `int` ⇒
    psycopg 让 PG 自己转（**绿**）⇒ asyncpg 直接报错
    （`invalid input for query argument $9: 1 (expected str, got int)`）
    ⇒ ⇒ **生产上必炸、车道里却绿** ⇒ ⇒ 一整类「类型不匹配」缺陷隐形。

    ⇒ 同步部分（建 schema / 跑 alembic）**仍用 psycopg**（asyncpg 没有同步 API）。
    """
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _async_engine(url: str, schema: str):
    """asyncpg 引擎（= 生产驱动）+ **隔离 schema**。

    ⚠️ **asyncpg 不认 `options=-csearch_path=`**（那是 libpq/psycopg 的参数）
    ⇒ `TypeError: connect() got an unexpected keyword argument 'options'`
    ⇒ ⇒ 隔离 schema 走 **启动参数 `server_settings={'search_path': …}`**
    （`search_path` 是 PGC_USERSET ⇒ 允许在启动包里设）。
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(
        _async_url(url),
        connect_args={"server_settings": {"search_path": schema}},
    )


# ---------------------------------------------------------------------------
# fixture：隔离 schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_schema() -> str:
    """隔离 schema 名（`e2e_<8hex>`）；建 schema → 迁移 → 测完 DROP。

    ⚠️ **起手先 `DROP SCHEMA IF EXISTS … CASCADE`** ⇒ 上次 DROP 失败留下的
    残留不会让这次「schema 已存在」直接炸。
    """
    from sqlalchemy import create_engine, text

    url = _lane_url()
    schema = f"e2e_{uuid.uuid4().hex[:8]}"
    engine = create_engine(url)
    try:
        # ⚠️ **真判据**（P10-B 评审 #8）：**真实连接**的库名（`current_database()`）
        # ⇒ ⇒ 必须在白名单 ⇒ ⇒ 否则**连开发库 `pcs` 都会被建 schema**。
        # ⚠️ 放在 `CREATE SCHEMA` **之前** ⇒ 拒绝时不留任何痕迹。
        with engine.connect() as conn:
            live_db = conn.execute(text("SELECT current_database()")).scalar_one()
        assert_allowed_lane_database(live_db, purpose="E2E 车道（真实连接）")

        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))

        # ⚠️ **迁移必须在子进程里跑** —— `alembic/env.py` 用
        # `settings.database_url`（pydantic-settings：**环境变量优先于 .env**）
        # ⇒ 把 scoped URL 放进子进程的 `DATABASE_URL` 就能建到隔离 schema。
        # ⚠️ `settings` 是 **pydantic 缓存实例** ⇒ 同一进程内第二次改环境变量
        # **不生效** ⇒ 子进程是唯一可靠的做法。
        upgraded = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env={**os.environ, "DATABASE_URL": _scoped_url(url, schema)},
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert upgraded.returncode == 0, (
            f"隔离 schema {schema} 的 `alembic upgrade head` 失败：\n"
            f"{upgraded.stdout}\n{upgraded.stderr}"
        )
        yield schema
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


# ---------------------------------------------------------------------------
# fixture：种子（⚠️ T1 阶段只有常量，行为在 T2）
# ---------------------------------------------------------------------------


# ⚠️ `loop_scope="session"` 是**必须**的 —— `asyncio_default_fixture_loop_scope`
# 是 `function` ⇒ session 级异步 fixture 若不显式声明自己的 loop scope ⇒
# pytest-asyncio 报 `ScopeMismatch`（session 请求了 function 级的 runner）。
# ⇒ 种子在**会话循环**里跑 ⇒ 客户端在**函数循环**里跑 ⇒ 两个引擎各活各的
# ⇒ 不跨循环 ⇒ 没有 bug-2162 那类「attached to a different loop」。
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def e2e_seed(e2e_schema) -> dict[str, object]:
    """把**流程级种子灌进隔离 schema**，返回种子 id 字典。

    ⚠️ **必须灌在隔离 schema 里** —— 灌到 public ⇒ 开发库被测试数据污染
    ⇒ 而症状是「跑得挺快、全绿」⇒ 没人发现（守卫已钉住 public 不变）。
    ⇒ ⚠️ **id 来自 `scripts/seed_e2e_flows.py` 的模块级常量**
    ⇒ 不另造一份「id 从哪来」的真相源。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.token_issuer import derive_user_id
    from scripts.seed_e2e_flows import (
        FLOW_DELIVERABLE_ID,
        FLOW_EQUIPMENT_ID,
        FLOW_MATRIX_ID,
        FLOW_PROJECT_ID,
        FLOW_RECORD_ID,
        FLOW_REPORT_DEF_ID,
        FLOW_STREAM_IDS,
        FLOW_WORKSPACE_ID,
        seed_flows,
    )

    # ⚠️ **自己建引擎、用完就 dispose** —— 不与 `e2e_client` 共用：
    # `asyncio_default_fixture_loop_scope = "function"` ⇒ session 级 fixture
    # 与 function 级测试**不在同一个事件循环** ⇒ 共用引擎 ⇒ 连接跨循环 ⇒
    # asyncpg 报「attached to a different loop」（bug-2162 同形）。
    # ⇒ 种子提交完就把引擎销毁 ⇒ 客户端用自己的引擎读**已提交**的行。
    engine = _async_engine(_lane_url(), e2e_schema)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await seed_flows(session)
    finally:
        await engine.dispose()

    return {
        "project_id": FLOW_PROJECT_ID,
        "workspace_id": FLOW_WORKSPACE_ID,
        "matrix_id": FLOW_MATRIX_ID,
        "deliverable_id": FLOW_DELIVERABLE_ID,
        "record_id": FLOW_RECORD_ID,
        "report_def_id": FLOW_REPORT_DEF_ID,
        "equipment_id": FLOW_EQUIPMENT_ID,
        # ⚠️ **源物流的 id**（有序）⇒ 计算链场景拿它当输入
        "stream_ids": list(FLOW_STREAM_IDS),
        # ⚠️ **用户 id**（用户名 → 派生 id）⇒ 任务体需要 `user_id`
        "users": {
            name: derive_user_id(name)
            for name in ("e2e-designer", "e2e-checker", "e2e-reviewer", "e2e-approver", "e2e-admin")
        },
    }


# ---------------------------------------------------------------------------
# fixture：真 app 客户端
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def e2e_client(e2e_schema, public_baseline):
    """`httpx.AsyncClient` ⇒ **真 app**（`create_app()`）+ `get_db` 覆盖到隔离 schema。

    ⚠️ **不用 `strict_client` 那套最小 app** —— E2E 要**真中间件链**
    （审计 / trace / CORS）⇒ 场景验的是**生产同款**行为。
    ⚠️ **不走 lifespan** ⇒ `httpx.ASGITransport` 本来就不跑 lifespan ⇒
    ⇒ 「只有 lifespan 才会做的那两处 seed」（**系数表** + **系统参数**）
    ⇒ ⇒ 由 **`scripts/seed_e2e_flows.py` 显式调生产用的那两个函数**补上
    ⇒ ⇒（P10-B 评审 #18 · 裁决选 (b)）⇒ ⇒ 隔离 schema 里**有生产默认数据**
    ⇒ ⇒ 车道验的是「生产同款」。
    ⚠️ **不跑完整 lifespan** —— ARQ worker / 信号在测试进程里是**噪音**
    ⇒ ⇒ 车道要的是「有生产默认数据」，不是「完整跑一遍生产启动」。

    ⚠️ **依赖 `public_baseline`**（P10-F · 评审 #22）—— ⇒ 它在**第一个** E2E
    用例之前就建立（session 级）⇒ ⇒ 会话级基线圈住的是**整个车道**
    ⇒ ⇒ 而不是「从某个用例才开始」的那一段。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_db
    from app.main import create_app

    # ⚠️ 引擎是**function 级**的（与本测试同一个事件循环）⇒ 不跨作用域复用
    engine = _async_engine(_lane_url(), e2e_schema)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db

    # ⚠️ **进程级 session factory 也必须指向隔离 schema**（P10-B 评审 #19 · P1）
    # ⇒ `app/db/session.py::get_async_session_factory()` 是**模块级单例**
    # ⇒ 只改 `get_db` ⇒ 下面两条路径读写的是 **pcs_pgtest 的 public schema**：
    #   · `app/api/v1/ws.py:77`（WS 握手鉴权）
    #   · `app/core/errors.py`（RBAC 拒绝的审计行 —— 评审 #10 的落点）
    # ⇒ ⇒ 「真 app + 真库 + 同款路径」在那两条路径上**不成立**
    # ⇒ ⇒ 这里把模块级单例也换成隔离 schema 的 engine/factory（测完还原）。
    import app.db.session as db_session_mod

    prev_engine = db_session_mod._async_engine
    prev_factory = db_session_mod._async_session_factory
    db_session_mod._async_engine = engine
    db_session_mod._async_session_factory = factory

    # ⚠️ **第三个单例也必须指向隔离 schema**（P10-F · 评审 #22）
    # ⇒ `app/db/session.py::get_engine()` 用的 `_sync_engine` 是**模块级单例**
    # ⇒ ⇒ #19 只覆写了两个 async 的 ⇒ ⇒ **任何走 `get_engine()` 的路径在车道里
    # 读写的是 public**（今天 `get_engine()` 只被 `check_database()` 用 ⇒
    # **还没有活的泄漏路径** ⇒ ⇒ 它是**未来泄漏点** ⇒ ⇒ 现在就堵住）。
    # ⚠️ **同步引擎的 schema 绑定与 async 不同** —— async 侧用
    # `server_settings={'search_path': …}`（asyncpg 不认 `options=`），
    # 同步侧用 **psycopg 的 `options=-csearch_path=…`** ⇒ ⇒ 两者不可混抄。
    from sqlalchemy import create_engine

    prev_sync_engine = db_session_mod._sync_engine
    sync_engine = create_engine(
        _lane_url(),
        connect_args={"options": f"-csearch_path={e2e_schema}"},
    )
    db_session_mod._sync_engine = sync_engine

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 供「直查隔离 schema」的用例用（不能靠 app 的 engine —— 它被
            # search_path 覆盖了 ⇒ 查 public 永远查不到 ⇒ 守卫恒绿 = 空壳）
            client._e2e_session_factory = factory  # type: ignore[attr-defined]
            yield client
    finally:
        db_session_mod._async_engine = prev_engine
        db_session_mod._async_session_factory = prev_factory
        db_session_mod._sync_engine = prev_sync_engine
        app.dependency_overrides.clear()
        sync_engine.dispose()
        await engine.dispose()


# ---------------------------------------------------------------------------
# fixture：public schema 的快照与基线（P10-F · 评审 #22）
# ---------------------------------------------------------------------------


@pytest.fixture
def public_engine():
    """**独立连接**到 public schema 的同步引擎（**不带** search_path 覆盖）。

    ⚠️ **必须独立连接** —— 用 app 的 engine 查 public **永远查不到**
    ⇒ ⇒ 守卫恒绿 = 空壳（hermes 断言形状病 #4）。
    """
    from sqlalchemy import create_engine

    from tests.e2e_flows.helpers import public_sync_url

    engine = create_engine(public_sync_url())
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def public_first_snapshot(e2e_schema):
    """public schema 的**第一时刻**快照（session 级）。

    ⚠️ **谁先谁后由依赖图定** —— `public_baseline` 依赖本 fixture ⇒ ⇒
    本快照**必然**先于基线快照 ⇒ ⇒ 两者不等 ⇒ 就是「中间有东西写了 public」。
    """
    from sqlalchemy import create_engine

    from tests.e2e_flows.helpers import public_snapshot, public_sync_url

    engine = create_engine(public_sync_url())
    try:
        return public_snapshot(engine)
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def public_baseline(public_first_snapshot):
    """public schema 的 **session 级基线** ⇒ 会话结束时**逐张相等**。

    ⚠️ **为什么是 session 级**：单条写路径的前后快照只断「那一条写路径」⇒ ⇒
    **别的**写路径（将来新加的）不受管 ⇒ ⇒ session 级基线把**整个车道**
    都圈进来 ⇒ ⇒ 与「单条写路径守卫」**并存**（两种口径，各管各的）。

    ⚠️ **取快照的时机**：`e2e_schema` 就绪之后（本 fixture 依赖它 ⇒ 它先建好）
    ⇒ ⇒ 会话开始时的 public 就是「车道动手之前」的 public。
    """
    from sqlalchemy import create_engine

    from tests.e2e_flows.helpers import public_snapshot, public_sync_url

    engine = create_engine(public_sync_url())
    baseline = public_snapshot(engine)
    try:
        yield baseline
    finally:
        after = public_snapshot(engine)
        engine.dispose()
        assert baseline == after, (
            "public schema 在 E2E 车道期间被改了 ⇒ 隔离失效："
            f"{_diff_tables(baseline, after)}"
        )


def _diff_tables(before: dict, after: dict) -> list[str]:
    """两张 public 快照的差异（表名 + 前后的值）⇒ 便于定位。"""
    out: list[str] = []
    for table in sorted(set(before) | set(after)):
        b, a = before.get(table), after.get(table)
        if b != a:
            out.append(f"{table}: {b} → {a}")
    return out


# ---------------------------------------------------------------------------
# fixture：角色 token
# ---------------------------------------------------------------------------


@pytest.fixture
def role_headers():
    """工厂 fixture ⇒ `role_headers("APPROVER")` ⇒ `{"Authorization": "Bearer …"}`。

    ⚠️ **`sub` 必须是 username** ⇒ actor 的 `user_id` 派生才对得上
    （`app/api/v1/config.py::current_actor` ⇒ `uuid5(NAMESPACE_DNS, sub)`）。
    ⚠️ **角色 → 用户的映射是唯一的**（来自 `scripts/seed_e2e_flows.py`）
    ⇒ 只解析**有授权**的人 ⇒ 局外人必须**显式点名**。
    """

    def _make(role: str | None = None, *, username: str | None = None) -> dict[str, str]:
        from app.core.security import create_access_token
        from scripts.seed_e2e_flows import ROLE_TO_USERNAME, USERNAME_TO_ROLE

        if username is None:
            if role is None:
                raise ValueError("role_headers() 必须给 role 或 username")
            if role not in ALLOWED_ROLES:
                raise ValueError(
                    f"角色 {role!r} 不在白名单里（允许：{sorted(ALLOWED_ROLES)}）"
                )
            if role not in ROLE_TO_USERNAME:
                raise ValueError(
                    f"角色 {role!r} 没有对应的种子用户（有的：{sorted(ROLE_TO_USERNAME)}）"
                    "⇒ 局外人必须显式点名 role_headers(username=…)"
                )
            username = ROLE_TO_USERNAME[role]

        if username not in USERNAME_TO_ROLE:
            raise ValueError(f"种子里没有用户 {username!r}")
        token_role = USERNAME_TO_ROLE[username]
        if token_role not in ALLOWED_ROLES:
            raise ValueError(f"用户 {username!r} 的角色 {token_role!r} 不在白名单里")
        token = create_access_token(subject=username, role=token_role)
        return {"Authorization": f"Bearer {token}"}

    return _make
