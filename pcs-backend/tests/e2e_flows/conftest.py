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
    return url


def _scoped_url(url: str, schema: str) -> str:
    """隔离 schema 的 URL = 原 URL **追加** `options=-csearch_path=<schema>`。

    ⚠️ `?` 还是 `&` 看原 URL 有没有 query（照
    `tests/api/v1/test_stream_batch_concurrency_pg.py` 的判据 ⇒ 抄错会建到 public）。
    """
    return url + ("&" if "?" in url else "?") + f"options=-csearch_path={schema}"


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
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from scripts.seed_e2e_flows import (
        FLOW_DELIVERABLE_ID,
        FLOW_MATRIX_ID,
        FLOW_PROJECT_ID,
        FLOW_RECORD_ID,
        FLOW_REPORT_DEF_ID,
        FLOW_WORKSPACE_ID,
        seed_flows,
    )

    # ⚠️ **自己建引擎、用完就 dispose** —— 不与 `e2e_client` 共用：
    # `asyncio_default_fixture_loop_scope = "function"` ⇒ session 级 fixture
    # 与 function 级测试**不在同一个事件循环** ⇒ 共用引擎 ⇒ 连接跨循环 ⇒
    # asyncpg 报「attached to a different loop」（bug-2162 同形）。
    # ⇒ 种子提交完就把引擎销毁 ⇒ 客户端用自己的引擎读**已提交**的行。
    engine = create_async_engine(_scoped_url(_lane_url(), e2e_schema))
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
    }


# ---------------------------------------------------------------------------
# fixture：真 app 客户端
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def e2e_client(e2e_schema):
    """`httpx.AsyncClient` ⇒ **真 app**（`create_app()`）+ `get_db` 覆盖到隔离 schema。

    ⚠️ **不用 `strict_client` 那套最小 app** —— E2E 要**真中间件链**
    （审计 / trace / CORS）⇒ 场景验的是**生产同款**行为。
    ⚠️ **不走 lifespan** ⇒ `httpx.ASGITransport` 本来就不跑 lifespan ⇒
    「只有 lifespan 才会做的那两处 seed」由 `e2e_seed` 显式补（T2 起）。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.session import get_db
    from app.main import create_app

    # ⚠️ 引擎是**function 级**的（与本测试同一个事件循环）⇒ 不跨作用域复用
    engine = create_async_engine(_scoped_url(_lane_url(), e2e_schema))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 供「直查隔离 schema」的用例用（不能靠 app 的 engine —— 它被
        # search_path 覆盖了 ⇒ 查 public 永远查不到 ⇒ 守卫恒绿 = 空壳）
        client._e2e_session_factory = factory  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


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
