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

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.e2e_flows.helpers import public_snapshot, purge_probe_rows, take_public_baseline

BACKEND_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# E2E 车道专属（真 PG · 隔离 schema）
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_lane_schema_is_migrated(e2e_client, e2e_schema):
    """隔离 schema 已 `alembic upgrade head` ⇒ 迁移产物在位。

    ⚠️ 断的是**迁移产物**（`alembic_version` + 核心业务表），
    「种子在不在」由下面那条断。
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
async def test_lane_seed_is_in_place(e2e_client, e2e_seed, role_headers):
    """⚠️ **种子在位** —— 隔离 schema 里真有那个项目。

    ⇒ `GET /api/v1/projects/{project_id}` 返回 **200** 且项目名是种子那个。

    ⚠️ **用 `e2e-designer` 的 token**（不是 SYSTEM_ADMIN）⇒ 顺带验了
    **授权行真的生效** —— 种子只造项目不造 `UserProject` ⇒ 这一条会 **404**
    （与「不存在」逐字同形）⇒ 而 404 在这个系统里**长得和「资源不存在」一样**
    ⇒ 极难定位。
    """
    resp = await e2e_client.get(
        f"/api/v1/projects/{e2e_seed['project_id']}",
        headers=role_headers("DESIGNER"),
    )
    assert resp.status_code == 200, (
        f"读种子项目返回 {resp.status_code}（body={resp.text[:200]}）"
        "⇒ 种子没在位，或授权行没生效（404 = 与「不存在」同形）"
    )
    assert resp.json()["project_name"] == "E2E Flows Project"


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
async def test_lane_never_writes_to_the_public_schema(
    e2e_client, e2e_schema, role_headers, public_engine
):
    """⚠️ **「隔离」这句话必须被验** —— E2E 的行**不能**出现在 public schema。

    ⚠️ **断法必须换**（2026-11-16 · hermes 断言形状病 #4）：
    **不能用「被覆盖过的 app engine」去查 public** —— 那个 engine 的
    `search_path` 指向隔离 schema ⇒ 查 public **永远查不到** ⇒ 守卫**恒绿** = 空壳。
    ⇒ 改用**独立连接**（不带 `options=-csearch_path=`）⇒ 取**写路径前后**的
    快照 ⇒ **断言不变**。
    ⇒ 且本用例**自己先走一遍真写路径** ⇒ 否则库里本来就没新行 ⇒ 照样恒绿。
    ⇒ ⚠️ **写必须真的成功**（201）—— 允许 422 等「失败」等于允许「什么都没写」
    ⇒ 那时「public 不变」只是「没写」的同义反复 ⇒ 守卫仍是空壳。

    ⚠️ **快照覆盖面**（P10-F · 评审 #22 · D3）：现在快照的是 public 的
    **全部表**（表清单来自 `information_schema`）⇒ ⇒ 不需要手抄「车道会写哪些表」
    ⇒ ⇒ 抄一次就漂一次那个病直接消失。
    """
    import uuid as _uuid

    from app.models.project import Workspace

    # ① 隔离 schema 里建一个 FORMAL 工作区（建项目的 FK 前置）
    async with e2e_client._e2e_session_factory() as session:  # type: ignore[attr-defined]
        workspace = Workspace(workspace_type="FORMAL", name="隔离守卫用工作区")
        session.add(workspace)
        await session.commit()
        # ⚠️ `expire_on_commit=False` ⇒ commit 后属性仍可读
        workspace_id = workspace.workspace_id

    before = public_snapshot(public_engine)
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
    after = public_snapshot(public_engine)

    assert before == after, f"public schema 被 E2E 改了：{before} → {after}"


# ---------------------------------------------------------------------------
# 守卫**自证**（P10-F · 评审 #22 · D10）—— 「它看得见泄漏」必须有证据
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_public_guard_detects_a_leaked_row(public_engine):
    """守卫自证：往 public **插一行** ⇒ 快照必须变化 ⇒ 否则它是空壳。

    ⚠️ **探针表选 `audit_logs`** —— 它**不在**旧守卫数的 4 张表里
    （users / projects / streams / user_projects）⇒ ⇒ 旧守卫**看不见**它
    ⇒ ⇒ 这条对「覆盖面不够」有证明力。

    ⚠️ **必须清理**：探针行删掉后，表里活着的行数与 `max(xmin)` 都回到原样
    ⇒ ⇒ session 级基线（会话结束逐张相等）才不会红。
    """
    _purge_probe_rows(public_engine)
    before = public_snapshot(public_engine)
    with public_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public.audit_logs (audit_id, action, resource_type) "
                "VALUES (gen_random_uuid(), 'E2E_LEAK_PROBE', 'PROBE')"
            )
        )
    after = public_snapshot(public_engine)
    assert before["audit_logs"] != after["audit_logs"], (
        "往 public 写了一行，快照却没变 ⇒ 守卫是空壳（连插都看不见）"
    )

    # ⚠️ **删除也必须看得见**（另一半的捕获能力）
    with public_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.audit_logs WHERE action = 'E2E_LEAK_PROBE'")
        )
    deleted = public_snapshot(public_engine)
    assert after["audit_logs"] != deleted["audit_logs"], (
        "删掉那一行，快照却没变 ⇒ 守卫是空壳（连删都看不见）"
    )
    assert deleted["audit_logs"] == before["audit_logs"], (
        "探针行删掉后快照**必须**回到原样 ⇒ 否则 session 级基线会误红"
    )


@pytest.mark.e2e
async def test_public_guard_detects_an_updated_row(public_engine):
    """⚠️ **UPDATE 是本任务的核心** —— `count(*)` **不变** ⇒ 只有 `max(xmin)` 看得见。

    ⇒ ⇒ 「同表内的替换与更新」是旧守卫的**真盲区**（只断 `count(*)`）。
    """
    _purge_probe_rows(public_engine)
    before = public_snapshot(public_engine)
    with public_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public.audit_logs (audit_id, action, resource_type) "
                "VALUES (gen_random_uuid(), 'E2E_LEAK_PROBE', 'PROBE')"
            )
        )
    inserted = public_snapshot(public_engine)
    with public_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE public.audit_logs SET resource_type = 'PROBE-UPDATED' "
                "WHERE action = 'E2E_LEAK_PROBE'"
            )
        )
    updated = public_snapshot(public_engine)

    assert inserted["audit_logs"][0] == updated["audit_logs"][0], (
        "UPDATE 不改行数 ⇒ 行数必须一样（否则这条测的不是 UPDATE）"
    )
    assert inserted["audit_logs"] != updated["audit_logs"], (
        "UPDATE 之后快照没变 ⇒ 守卫看不见**同表内的更新**（只断 count(*) 的老盲区）"
    )

    with public_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.audit_logs WHERE action = 'E2E_LEAK_PROBE'")
        )
    assert public_snapshot(public_engine)["audit_logs"] == before["audit_logs"], (
        "探针行删掉后快照**必须**回到原样 ⇒ 否则 session 级基线会误红"
    )


@pytest.mark.e2e
async def test_public_baseline_is_taken_before_any_lane_write(
    public_first_snapshot, public_baseline
):
    """基线必须**早于**车道的任何写入 ⇒ ⇒ 两份「最初时刻」的快照必须相等。

    （若中间有写入 ⇒ 不等 ⇒ 顺序被写错时这条立刻红。）
    """
    assert public_first_snapshot == public_baseline, (
        "两份「最初时刻」的快照不相等 ⇒ 中间有东西写了 public"
    )


@pytest.mark.e2e
async def test_baseline_purges_probe_rows_left_by_a_crashed_run(public_engine):
    """⚠️ **上一次跑崩了留下的探针行，必须在取基线之前清掉**（评审 I4）。

    ⇒ ⇒ 探针行是**真的写进 public** 的 ⇒ ⇒ 某条断言红了 ⇒ ⇒ 清理那步
    ⇒ ⇒ 没跑到 ⇒ ⇒ **残留**。
    ⇒ ⇒ 下一次跑：`public_baseline` 在会话开始取（**含**残留）⇒ ⇒
    ⇒ 探针用例把残留删掉 ⇒ ⇒ 会话结束时「基线 == 现状」**不等** ⇒ ⇒ **红**
    ⇒ ⇒ 而红的原因与车道行为**无关**（是上一次崩了）。
    ⇒ ⇒ ⇒ **守卫真的抓漏的那一次，恰恰是最容易把下一次跑带偏的那一次**。
    """
    # ① 造残留（模拟上一次跑崩了）
    with public_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public.audit_logs (audit_id, action, resource_type) "
                "VALUES (gen_random_uuid(), 'E2E_LEAK_PROBE', 'PROBE')"
            )
        )

    # ② 基线必须**先清残留**再取快照
    baseline = take_public_baseline(public_engine)

    with public_engine.connect() as conn:
        left = conn.execute(
            text("SELECT count(*) FROM public.audit_logs WHERE action = 'E2E_LEAK_PROBE'")
        ).scalar_one()
    assert left == 0, (
        "取基线之前没清探针残留 ⇒ 上一次崩了会把下一次跑带偏（假红）"
    )

    # ③ 基线里也不该含残留（行数 = 表里的真实行数）
    with public_engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM public.audit_logs")).scalar_one()
    assert baseline["audit_logs"][0] == total, (
        f"基线里的 audit_logs 行数 {baseline['audit_logs'][0]} ≠ 实际 {total}"
        " ⇒ 基线是在清残留**之前**取的 ⇒ ⇒ 下一次跑必假红"
    )


@pytest.mark.e2e
async def test_sync_engine_singleton_is_bound_to_the_isolated_schema(
    e2e_client, e2e_schema
):
    """⚠️ **第三个单例**（`_sync_engine`）也必须指向隔离 schema（P10-F · 评审 #22）。

    ⚠️ #19 只覆写了两个 async 单例 ⇒ ⇒ **任何走 `get_engine()` 的路径在车道里
    读写的是 public** ⇒ ⇒ 今天 `get_engine()` 只被 `check_database()` 用
    ⇒ ⇒ **还没有活的泄漏路径** ⇒ ⇒ 它是**未来泄漏点** ⇒ ⇒ 现在就堵住。

    ⇒ ⇒ 断**行为**（真连一次看 `current_schema()`）而不是断「某行代码存在」。
    """
    import app.db.session as db_session_mod

    engine = db_session_mod._sync_engine
    assert engine is not None, (
        "同步引擎单例没有被覆写 ⇒ 任何走 `get_engine()` 的路径都读写 public"
    )
    with engine.connect() as conn:
        current = conn.execute(text("SELECT current_schema()")).scalar_one()
    assert current == e2e_schema, (
        f"同步引擎落在 schema {current!r}（应是隔离 schema {e2e_schema!r}）"
        "⇒ 走 `get_engine()` 的路径会写 public"
    )


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
    """public schema 的**同步** URL（**不带** `options=-csearch_path=`）。

    ⚠️ 真相源已挪到 `tests/e2e_flows/helpers.py::public_sync_url`
    ⇒ 这里保留一个薄壳 ⇒ 免得两处各写一份 URL 改法。
    """
    from tests.e2e_flows.helpers import public_sync_url

    return public_sync_url()


def _purge_probe_rows(engine) -> None:
    """删掉**上一次**跑剩下的探针行（幂等自洁）。

    ⚠️ **真相源在 `tests/e2e_flows/helpers.py::purge_probe_rows`**
    ⇒ ⇒ 这里只做转发（⇒ ⇒ 免得两处各写一份 SQL ⇒ ⇒ 抄一次就漂一次）。
    """
    purge_probe_rows(engine)


def text_(sql: str):
    """`sqlalchemy.text` 的短别名（避免在函数体里到处 import）。"""
    from sqlalchemy import text

    return text(sql)


