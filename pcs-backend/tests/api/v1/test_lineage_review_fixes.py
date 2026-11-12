"""P9B-4 评审的**血缘面**修复（#3 / #4 / #9 / #11）。

## 为什么单独一个文件

`test_lineage_by_source_ref.py` 已经 705 行 ⇒ 再加会破 800 行（仓库约定）
⇒ 本文件只放**评审带回来的那几条**，自带最小 fixtures。

## 本文件钉的四条

1. **#9 守卫注册表不缺类型** —— 「能写出血缘行的模型」必须**逐个**在
   `LINEAGE_GUARDED_RECORD_TYPES` 里 ⇒ 否则 fail-closed 把它变成**永久 404**
   （本批的 `PsvResult` 就是这样：它**不在** `RECORD_TYPE_REGISTRY` 里 ——
   那张表是**表枚举**，不是写入方清单 —— 但 `psv_persist.py` 确实写它的血缘行，
   且 `psv.py` 确实读回同一批行 ⇒ **有活跃消费方**）。
   ⚠️ 契约测试的判据用「**有 `project_id` 且有 `record_hash`** 的计算结果模型」
   ⇒ **不依赖** `RECORD_TYPE_REGISTRY`（那张表的模块 docstring 明写它
   **不是** `finalize_calc_record` 的支持清单）⇒ 将来新增一个计算结果表
   而忘了登记 ⇒ 这条测试立刻红。
2. **#3 角色门** —— 血缘端点必须与物流端点**同一条角色白名单**
   （用户 2026-11-12 裁决：沿用 streams 白名单）⇒ 否则 `VIEWER` / `REVIEWER`
   从 `GET /streams/{id}` 拿 403、却从 `GET /lineage/streams/{id}/graph` 拿 200。
3. **#4 一行一种表示** —— 同一条血缘行在 `/graph` 与 `/upstream` / `/downstream`
   上必须**逐字同形**（时间戳字符串当前是 `...Z` 与 `...+00:00` 两种）。
4. **#11 逐字同形的 404 要被钉住** —— 「未登记类型」与「记录不存在」
   的响应体（code + message）必须**完全相同** ⇒ 「未登记类型」不能成为
   一个可枚举信号。
   ⚠️ 这几条是**钉子**（pin）：当前行为已经正确 ⇒ 它们**本来就该绿**
   ⇒ 作用是「将来有人改文案/改信封 ⇒ 立刻红」，不是修一个当下的缺陷。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="lineage-fix", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "lineage-fix")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="血缘评审修复测试",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession):
    async def _make(project: Project, **overrides) -> Stream:
        payload = {
            "project_id": project.project_id,
            "workspace_id": project.workspace_id,
            "stream_name": f"S-{uuid.uuid4().hex[:6]}",
            "case_type": "NORMAL",
            "data_mode": "CHEMICAL",
            "source_type": "MANUAL_ENTRY",
            "approval_depth": 1,
        }
        payload.update(overrides)
        stream = Stream(**payload)
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


async def _make_calc_row(db: AsyncSession, model: type, project: Project):
    """造一行该类型的计算记录（**只填必填列**）⇒ 守卫能按 pk 找到它。"""
    from app.models.psv_standards import ProjectCalculationStandardProfile  # noqa: F401

    payload: dict = {}
    for col in model.__table__.columns:
        if col.nullable or col.default is not None or col.server_default is not None:
            continue
        t = col.type
        name = col.name
        if name == "profile_code":
            value = "API"
        elif name == "discipline":
            value = "PSV"
        elif name == "circulation_type":
            value = "HORIZONTAL"
        elif t.__class__.__name__ == "Enum":
            value = t.enums[0]
        elif "JSON" in t.__class__.__name__:
            value = {}
        elif t.__class__.__name__ == "Uuid":
            value = uuid.uuid4()
        elif t.__class__.__name__ == "Boolean":
            value = True
        elif t.__class__.__name__ in ("Float", "Numeric"):
            value = 1.0
        elif t.__class__.__name__ == "Integer":
            value = 1
        elif t.__class__.__name__ == "DateTime":
            value = datetime.now(UTC)
        elif t.__class__.__name__ in ("String", "Text"):
            value = f"TEST-{uuid.uuid4().hex[:6]}"
        else:
            value = None
        assert value is not None, f"{model.__name__}.{name} 没有哑值"
        payload[name] = value
    payload["project_id"] = project.project_id
    if "workspace_id" in model.__table__.columns:
        payload["workspace_id"] = project.workspace_id
    row = model(**payload)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def _make_lineage_row(
    db: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    source_ref: Stream | None = None,
    occurred_at: datetime | None = None,
) -> DataLineage:
    payload: dict = {
        "record_type": record_type,
        "record_id": record_id,
        "source": "CALC",
        "change_summary": "calc finalize",
    }
    if source_ref is not None:
        payload["source_ref_type"] = "Stream"
        payload["source_ref_id"] = source_ref.stream_id
    if occurred_at is not None:
        payload["occurred_at"] = occurred_at
    row = DataLineage(**payload)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# #9 守卫注册表不缺类型
# ---------------------------------------------------------------------------


def _calc_result_models_with_project() -> list[type]:
    """**有 `project_id` 且有 `record_hash`** 的计算结果模型。

    ⚠️ 判据**不**用 `RECORD_TYPE_REGISTRY` —— 那张表是**表枚举**
    （`calc_lineage` 的模块 docstring 明写它**不是** `finalize_calc_record` 的
    支持清单）⇒ 用它当基准 ⇒ 漏登记的类型永远测不出来（本批 `PsvResult` 就是
    这样漏的）。
    """
    import app.models.calc as calc_mod
    import app.models.psv_standards as psv_mod

    out: list[type] = []
    for mod in (calc_mod, psv_mod):
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type) or not hasattr(obj, "__tablename__"):
                continue
            cols = {c.name for c in inspect(obj).columns}
            if "project_id" in cols and "record_hash" in cols:
                out.append(obj)
    return out


async def test_every_calc_result_model_is_registered_in_the_guard():
    """⚠️ **每一个能写血缘行的计算结果模型都必须在守卫注册表里**。

    ⇒ 否则 T0-D 的 fail-closed 把它变成**永久 404**（本批 `PsvResult` 就是
    这样：它**不在** `RECORD_TYPE_REGISTRY` 里 —— 那张表是**表枚举** ——
    但 `psv_persist.py` 确实写它的血缘行，`psv.py:247` 确实读回同一批行
    ⇒ **有活跃消费方**）。
    """
    from app.api.v1.lineage import LINEAGE_GUARDED_RECORD_TYPES

    missing = [
        m.__name__
        for m in _calc_result_models_with_project()
        if m.__name__ not in LINEAGE_GUARDED_RECORD_TYPES
    ]
    assert not missing, (
        f"这些模型能写出血缘行却没登记 ⇒ 血缘查询对它们**永久 404**：{missing}"
    )


async def test_psv_result_lineage_is_queryable(
    strict_client,
    db_session,
    make_project,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """`PsvResult` 有活跃消费方（`psv.py:247` 读同一批行）⇒ 血缘查询必须通。"""
    from app.models.calc import PsvResult

    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-fix")

    row = await _make_calc_row(db_session, PsvResult, project)
    await _make_lineage_row(
        db_session, record_type="PsvResult", record_id=row.psv_id
    )

    r = await strict_client.get(
        f"/api/v1/lineage/PsvResult/{row.psv_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["root"]["record_type"] == "PsvResult"


# ---------------------------------------------------------------------------
# #3 角色门（用户 2026-11-12 裁决：沿用 streams 白名单）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["VIEWER", "REVIEWER", "CHECKER"])
async def test_lineage_endpoints_use_the_streams_role_whitelist(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    role,
):
    """⚠️ 血缘端点必须与**物流端点**同一条角色白名单。

    否则：`VIEWER` / `REVIEWER` / `CHECKER`（都在 `current_actor` 的
    `_ALLOWED_ROLES` 里 ⇒ 能进 actor 层）从 `GET /streams/{id}` 拿 **403**，
    却从 `GET /lineage/streams/{id}/graph` 拿 **200**（还带上了物流自己的
    `source` / `created_by` / `created_at` 与下游计算血缘行）⇒
    **绕过物流面的角色门读到了物流面读不到的东西**。

    ⚠️ **角色门在项目守卫之前**（与 `streams.py` 的既有顺序一致）：
    角色判定**不看 id** ⇒ 任何 id 都得同一个 403 ⇒ 不泄漏存在性；
    反过来（先查项目）则 403 会泄漏「这个 id 在你有权限的项目里」。
    """
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"lineage-role-{role}")
    token = create_access_token(subject=f"lineage-role-{role}", role=role)
    headers = {"Authorization": f"Bearer {token}"}

    project = await make_project()
    await grant_project(user_id, project.project_id, username=f"lineage-role-{role}")
    stream = await make_stream(project)

    for suffix in ("graph", "upstream", "downstream"):
        r = await strict_client.get(
            f"/api/v1/lineage/streams/{stream.stream_id}/{suffix}", headers=headers
        )
        assert r.status_code == 403, (
            f"/lineage/streams/{{id}}/{suffix} 对角色 {role} 返回 "
            f"{r.status_code}（应 403，与物流端点同口径）⇒ {r.text}"
        )


# ---------------------------------------------------------------------------
# #4 一行一种表示
# ---------------------------------------------------------------------------


async def test_same_lineage_row_has_one_representation_across_endpoints(
    strict_client,
    db_session,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ 同一条血缘行在三个端点上必须**逐字同形**。

    现状：`/graph` 走具名 schema（pydantic 往返 ⇒ `2026-09-15T14:00:00Z`），
    `/upstream` / `/downstream` 走 `list[dict]`（`_serialize` 的 `isoformat()`
    ⇒ `2026-09-15T14:00:00+00:00`）⇒ **同一行的字符串随端点而变**
    ⇒ 客户端拿两个端点的数据对不上。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-fix")
    stream = await make_stream(project)

    occurred = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    row = await _make_lineage_row(
        db_session,
        record_type="PipingResult",
        record_id=uuid.uuid4(),
        source_ref=stream,
        occurred_at=occurred,
    )

    r_graph = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    r_down = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/downstream", headers=designer_headers
    )
    assert r_graph.status_code == 200, r_graph.text
    assert r_down.status_code == 200, r_down.text

    graph_node = r_graph.json()["downstream"][0]
    down_node = r_down.json()[0]
    assert graph_node["occurred_at"] == down_node["occurred_at"], (
        f"同一行的 occurred_at 两种表示：{graph_node['occurred_at']} vs "
        f"{down_node['occurred_at']}"
    )
    # ⚠️ 其它字段也要一致（字段集不同 ⇒ 将来 `_serialize` 加字段会被静默丢弃）
    assert set(graph_node) == set(down_node)
    assert graph_node["lineage_id"] == str(row.lineage_id)


# ---------------------------------------------------------------------------
# #11 逐字同形的 404（**钉子**：当前行为已对，本组用例的作用是「别再漂」）
# ---------------------------------------------------------------------------


async def test_unknown_record_type_404_is_byte_identical_to_not_found(
    strict_client, designer_headers
):
    """「未登记类型」与「记录不存在」的响应体必须**完全相同**。

    ⚠️ 「未登记类型」若与「不存在」不同形 ⇒ 它就成了一个**可枚举信号**
    ⇒ 攻击者能靠响应差异枚举出「哪些 record_type 受支持」。
    """
    r_unknown = await strict_client.get(
        f"/api/v1/lineage/NotARecordType/{uuid.uuid4()}/graph",
        headers=designer_headers,
    )
    r_missing = await strict_client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/graph", headers=designer_headers
    )
    assert r_unknown.status_code == 404
    assert r_missing.status_code == 404
    assert r_unknown.json() == r_missing.json(), (
        f"未登记类型与不存在的响应体不同 ⇒ 成了可枚举信号："
        f"{r_unknown.json()} vs {r_missing.json()}"
    )


@pytest.mark.parametrize("suffix", ["upstream", "downstream"])
async def test_unknown_record_type_404_on_siblings_is_identical(
    strict_client, designer_headers, suffix
):
    """`/upstream` 与 `/downstream` 的未登记类型也要**逐字同形**。

    ⚠️ 改前 `/upstream` 对未登记类型返 **200 + []**（守卫跳过）⇒
    与 `/graph` 的 404 **形状不同** ⇒ 「这个 record_type 不被支持」成了
    可枚举信号 ⇒ 本批把它改成 fail-closed ⇒ 这里钉住。
    """
    r_unknown = await strict_client.get(
        f"/api/v1/lineage/NotARecordType/{uuid.uuid4()}/{suffix}",
        headers=designer_headers,
    )
    r_missing = await strict_client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/{suffix}", headers=designer_headers
    )
    assert r_unknown.status_code == 404, r_unknown.text
    assert r_unknown.json() == r_missing.json()


async def test_upstream_for_streams_returns_empty_list(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """`record_type='streams'` 的 `/upstream` ⇒ **200 + 空数组**。

    ⚠️ 物流是**源** ⇒ 没有上游血缘行 ⇒ 「没有上游」与「不存在」是**两件事**
    ⇒ 不能用 404 表达。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-fix")
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/upstream", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert r.json() == []
