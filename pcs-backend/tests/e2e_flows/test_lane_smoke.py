"""E2E 车道的自检（隔离 schema · 真 PG）—— P10-B · T1。

## 这些用例守什么

1. **隔离 schema 真的迁移好了** —— 否则场景全在**没有表的库**上跑，
   而症状看起来像「端点坏了」。
2. **角色 token 对得上种子** —— 否则全场 404（症状离病因很远）。
3. **E2E 不写 public schema** —— 否则「隔离 schema」是空话，
   开发库数据被 E2E 污染而**没人知道**。
4. **默认车道必须跳过 `e2e`** —— 否则批末那句 `uv run pytest`
   会把 E2E 场景**跑到开发库 `pcs` 上**。

## ⚠️ 哪些用例在默认车道跑

带 `@pytest.mark.e2e` 的 ⇒ **只在 E2E 车道跑**（默认车道被闸门 skip）；
**不带 marker 的** ⇒ 默认车道也跑（它们不碰库）⇒
其中「闸门自己」那条必须在默认车道跑 —— 否则闸门坏了**没人发现**。

⚠️ **T1 阶段 `e2e_seed` 是桩**（`scripts/seed_e2e_flows.py` 的行为部分在 T2）
⇒ 用例 1 暂时只断「schema 迁移到位」⇒ T2 落地后补「种子在位」的断言。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# E2E 车道专属（真 PG · 隔离 schema）
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_lane_schema_is_migrated(e2e_client, e2e_schema):
    """隔离 schema 已 `alembic upgrade head` ⇒ 迁移产物在位。

    ⚠️ **T1 阶段只断「迁移到位」**（种子在 T2）⇒ 断的是**迁移产物**
    （`alembic_version` + 核心业务表），不是「有没有种子行」。
    """
    from sqlalchemy import text

    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        rows = (
            await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema ORDER BY table_name"
                ),
                {"schema": e2e_schema},
            )
        ).scalars().all()

    assert "alembic_version" in rows, f"隔离 schema {e2e_schema} 没有迁移产物"
    for table in ("users", "projects", "user_projects"):
        assert table in rows, f"隔离 schema {e2e_schema} 缺表 {table} ⇒ 迁移没跑全"


@pytest.mark.e2e
async def test_lane_role_headers_map_to_seeded_users(e2e_client, e2e_seed, role_headers):
    """每个全局角色都能用自己的 token 读到种子项目（200）⇒ 角色矩阵与种子对齐。

    ⚠️ T1 阶段种子是桩 ⇒ 断的是「**每个角色都能签出 token 且 token 能被解析**」
    （`role_headers` 返回的 Authorization 头能被 `current_actor` 接受）
    ⇒ T2 落地后补「读到种子项目 200」的断言。
    """
    from app.core.security import decode_token  # type: ignore[attr-defined]

    for role in ("DESIGNER", "CHECKER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN"):
        headers = role_headers(role)
        raw = headers["Authorization"].removeprefix("Bearer ")
        payload = decode_token(raw)
        assert payload["sub"], f"role_headers({role!r}) 的 token 没有 sub"
        assert payload["role"] == role


@pytest.mark.e2e
async def test_lane_never_writes_to_the_public_schema(e2e_client, e2e_schema, role_headers):
    """⚠️ **「隔离」这句话必须被验** —— E2E 的行**不能**出现在 public schema。

    ⚠️ **断法必须换**（2026-11-16 · hermes 断言形状病 #4）：
    **不能用「被覆盖过的 app engine」去查 public** —— 那个 engine 的
    `search_path` 指向隔离 schema ⇒ 查 public **永远查不到** ⇒ 守卫**恒绿** = 空壳。
    ⇒ 改用**独立连接**（不带 `options=-csearch_path=`）⇒ 取**写路径前后**的
    `count(*)` 快照 ⇒ **断言不变**。
    ⇒ 且本用例**自己先走一遍真写路径** ⇒ 否则库里本来就没新行 ⇒ 照样恒绿。
    ⇒ ⚠️ **写必须真的成功**（201）—— 允许 422 等「失败」等于允许「什么都没写」
    ⇒ 那时「public 不变」只是「没写」的同义反复 ⇒ 守卫仍是空壳。
    """
    import uuid as _uuid

    from sqlalchemy import create_engine

    from app.models.project import Workspace

    # ① 隔离 schema 里建一个 FORMAL 工作区（建项目的 FK 前置）
    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        workspace = Workspace(workspace_type="FORMAL", name="隔离守卫用工作区")
        session.add(workspace)
        await session.commit()
        # ⚠️ `expire_on_commit=False` ⇒ commit 后属性仍可读
        workspace_id = workspace.workspace_id

    public_engine = create_engine(_public_sync_url())
    try:
        before = _public_snapshot(public_engine)
        # ② 走一遍**真写路径**（建项目 ⇒ 会写 projects + user_projects）
        resp = await e2e_client.post(
            "/api/v1/projects",
            json={
                "project_no": f"E2E-GUARD-{_uuid.uuid4().hex[:8]}",
                "project_name": "隔离守卫用项目",
                "owner_company": "业主",
                "location": "地点",
                "project_type": "CHEMICAL",
                "design_phase": "FEED",
                "unit_system": "SI",
                "workspace_id": str(workspace_id),
            },
            # ⚠️ 建项目端点要求 **SYSTEM_ADMIN**（`require_roles`）⇒
            # 用 `e2e-admin` 的 token（`role_headers` 的映射里唯一那个）
            headers=role_headers("SYSTEM_ADMIN"),
        )
        assert resp.status_code in (200, 201), (
            f"写路径没走通（status={resp.status_code} body={resp.text[:200]}）⇒ "
            "本用例的「public 不变」就成空壳"
        )
        after = _public_snapshot(public_engine)
    finally:
        public_engine.dispose()

    assert before == after, f"public schema 被 E2E 改了：{before} → {after}"


# ---------------------------------------------------------------------------
# 默认车道也跑（不碰库）
# ---------------------------------------------------------------------------


def test_role_headers_rejects_an_unknown_role(role_headers):
    """未知角色 ⇒ **报错**（不是给一个错的 token ⇒ 全场 404 ⇒ 症状离病因远）。"""
    with pytest.raises(ValueError):
        role_headers("NOT_A_ROLE")


def test_role_headers_rejects_a_role_outside_the_allowlist(role_headers):
    """⚠️ 角色**在白名单外** ⇒ **报错** ⇒ 不是发一个非法 token 让全场 403。

    ⚠️ 顺带钉住「白名单本身」：本仓 copy 的集合必须**等于**应用里那份
    （`app/api/v1/config.py` 的 `_ALLOWED_ROLES`）⇒ 否则复制品会漂。
    """
    with pytest.raises(ValueError):
        role_headers("SYSADMIN")

    source = (BACKEND_ROOT / "app" / "api" / "v1" / "config.py").read_text(
        encoding="utf-8"
    )
    block = re.search(r"_ALLOWED_ROLES\s*=\s*\{(.*?)\}", source, re.S)
    assert block, "应用里找不到 `_ALLOWED_ROLES` ⇒ 白名单的口径变了"
    app_roles = set(re.findall(r'"([^"]+)"', block.group(1)))
    from tests.e2e_flows.conftest import ALLOWED_ROLES

    assert ALLOWED_ROLES == app_roles, (
        f"白名单漂移了：conftest={sorted(ALLOWED_ROLES)} app={sorted(app_roles)}"
    )


def test_e2e_items_are_skipped_without_the_lane_flag():
    """⚠️ **默认车道必须跳过 `e2e`**（hermes P0-2）—— 没有 `PCS_E2E_LANE=1`
    ⇒ `pytest_collection_modifyitems` 闸门给每个 `e2e` 用例打 skip 标记。

    ⇒ 断法：直接调闸门函数，传一个假 item ⇒ 断言 `add_marker(skip)` 被调过
    ⇒ **不**去真跑一次 `uv run pytest`（那太慢且会碰真库）。
    """
    from tests.e2e_flows.conftest import _skip_e2e_items_unless_in_lane

    class _FakeItem:
        def __init__(self) -> None:
            self.markers: list[object] = []

        def get_closest_marker(self, name: str):
            return object() if name == "e2e" else None

        def add_marker(self, marker) -> None:
            self.markers.append(marker)

    item = _FakeItem()
    # 闸门的签名就是 pytest 的 `pytest_collection_modifyitems(session, config, items)`
    _skip_e2e_items_unless_in_lane(None, None, [item])
    assert item.markers, "没有 PCS_E2E_LANE 时**没有**给 e2e 用例打 skip ⇒ 默认车道会误伤开发库"


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _public_sync_url() -> str:
    """public schema 的**同步** URL（**不带** `options=-csearch_path=`）。"""
    url = os.environ.get("DATABASE_URL") or ""
    assert url.startswith("postgres"), (
        f"不在 E2E 车道里（DATABASE_URL={url!r}）⇒ 本用例需要真 PG"
    )
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://").replace(
        "+asyncpg", "+psycopg"
    )


def _public_snapshot(engine) -> dict[str, int]:
    from sqlalchemy import text

    out: dict[str, int] = {}
    with engine.connect() as conn:
        for table in ("users", "projects", "streams", "user_projects"):
            out[table] = int(
                conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar_one()
            )
    return out


def text_(sql: str):
    """`sqlalchemy.text` 的短别名（避免在函数体里到处 import）。"""
    from sqlalchemy import text

    return text(sql)


