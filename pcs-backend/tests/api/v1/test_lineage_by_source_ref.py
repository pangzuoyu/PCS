"""物流血缘的「按源引用查」+ 合成 root —— P9B-4 T0-D（TODO-136）。

## 这个文件在钉什么

2026-11-10 实测：**写入方用类名**（`LineageTracker.track` 写
`record.__class__.__name__`），而物流在血缘里**只作为源引用**存在
（`source_ref_type='Stream'` + `source_ref_id=<物流 id>`）⇒ **从来没有**
`record_type='streams'` 的行 ⇒ 前端查 `record_type='streams'` ⇒ **永远空**。

⚠️ **只改拼写解决不了**（改完仍查不到行）⇒ 这是**补一种查询语义**。

## 本文件钉的四条

1. **按源引用查得到** —— 有以该物流为源的血缘行 ⇒ `/graph` 返回得到（不是 404），
   且那些行落在 **downstream**（物流是源 ⇒ 下游是它的产出）。
2. **合成 root** —— 物流**没有**自己的血缘行 ⇒ root 是**合成**的：
   **字段集与真实 root 相同**（不是最小集）+ **确定性 id** + 明确标注是合成。
3. **守卫不退化** —— 跨项目仍 **404**（与「不存在」**逐字同形**）。
4. **注册表完整 + fail-closed** —— 每个能写出血缘行的类型都在守卫注册表里；
   **未登记的类型 ⇒ 404**（与「不存在」同形，不是一个可枚举信号）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import (
    JSON as SAJSON,
)
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    Uuid as SAUuid,
)
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
    token = create_access_token(subject="lineage-src", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "lineage-src")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="血缘源引用测试",
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


@pytest_asyncio.fixture
async def make_source_ref_lineage(db: AsyncSession):
    """造一条「以物流为**源**」的血缘行（= `finalize_calc_record` 写的那种）。"""

    async def _make(
        stream: Stream,
        record_type: str = "PipingResult",
        occurred_at: datetime | None = None,
    ) -> DataLineage:
        payload = dict(
            record_type=record_type,
            record_id=uuid.uuid4(),
            source="CALC",
            source_ref_type="Stream",
            source_ref_id=stream.stream_id,
            change_summary="calc finalize",
        )
        if occurred_at is not None:
            payload["occurred_at"] = occurred_at
        row = DataLineage(**payload)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    return _make


# ---------------------------------------------------------------------------
# 1. 按源引用查得到（不是 404）
# ---------------------------------------------------------------------------


async def test_graph_returns_downstream_by_source_ref(
    strict_client,
    make_project,
    make_stream,
    make_source_ref_lineage,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """有以该物流为**源**的血缘行 ⇒ `/graph` **返回得到**（此前永远 404）。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)
    row = await make_source_ref_lineage(stream)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [d["lineage_id"] for d in body["downstream"]] == [str(row.lineage_id)]
    # 物流是**源** ⇒ 没有上游血缘行
    assert body["upstream"] == []


async def test_graph_without_any_lineage_row_is_still_200(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """没有任何血缘行 ⇒ 仍然 200（合成 root）—— 空图 ≠ 404。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["downstream"] == []
    assert body["upstream"] == []
    assert body["root"] is not None


# ---------------------------------------------------------------------------
# 1b. 下游**有上限**且**最新的在前**（整批评审 Important #2）
# ---------------------------------------------------------------------------


async def test_downstream_is_bounded_and_newest_first(
    strict_client,
    make_project,
    make_stream,
    make_source_ref_lineage,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ `data_lineage` **只增不删**（每次重算一行）⇒ 不限则响应**无界增长**。

    ⇒ 下游**有上限**（`max_depth`，默认 10）且**最新的在前**（`occurred_at DESC`）。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        await make_source_ref_lineage(
            stream, occurred_at=base + timedelta(hours=i)
        )
        for i in range(12)
    ]

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    down = r.json()["downstream"]
    # ⚠️ 上限 = `max_depth`（默认 10）⇒ 12 条只回 10 条
    assert len(down) == 10, f"下游没有上限：{len(down)} 条"
    # ⚠️ **最新的在前**
    assert down[0]["lineage_id"] == str(rows[-1].lineage_id)
    assert down[1]["lineage_id"] == str(rows[-2].lineage_id)


async def test_max_depth_caps_the_downstream_rows(
    strict_client,
    make_project,
    make_stream,
    make_source_ref_lineage,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """`?max_depth=2` ⇒ 下游只回 2 条（参数**真的**生效，不是摆设）。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        await make_source_ref_lineage(
            stream, occurred_at=base + timedelta(hours=i)
        )

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph?max_depth=2",
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["downstream"]) == 2


async def test_downstream_endpoint_also_caps_and_orders(
    strict_client,
    make_project,
    make_stream,
    make_source_ref_lineage,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ **`/downstream` 也要封顶**（整批评审复核发现的尾巴）。

    ⚠️ 此前只有 `/graph` 传了 `limit` ⇒ `/downstream` 仍返回**全部**历史重算行
    ⇒ 两个端点对**同一份数据**给出**不同的上限与顺序**（正是本批 Ruling 要
    消灭的「两个端点互相打脸」形状）⇒ 且它是个**公开端点**（外部脚本会撞上）。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        await make_source_ref_lineage(
            stream, occurred_at=base + timedelta(hours=i)
        )
        for i in range(5)
    ]

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/downstream?max_depth=2",
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    down = r.json()
    assert len(down) == 2, f"下游没封顶：{len(down)} 条"
    # ⚠️ **最新的在前**（与 `/graph` 同口径）
    assert down[0]["lineage_id"] == str(rows[-1].lineage_id)


# ---------------------------------------------------------------------------
# 2. 合成 root（形状 / 确定性 / 语义）
# ---------------------------------------------------------------------------


async def test_synthetic_root_fields(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """合成 root 的 10 个字段（与真实 root **同形**）取值正确。"""
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project, source="EXCEL")

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    root = r.json()["root"]

    assert root["record_type"] == "streams"
    assert root["record_id"] == str(stream.stream_id)
    assert root["parent_lineage_id"] is None
    # root 的 source = **物流来源**（4 值：怎么进系统的）
    assert root["source"] == "EXCEL"
    # 物流**就是**源 ⇒ 没有上游引用
    assert root["source_ref_type"] is None
    assert root["source_ref_id"] is None
    assert root["change_summary"], "合成 root 的变更摘要必须可读"
    assert root["occurred_at"]


async def test_synthetic_root_lineage_id_is_deterministic(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """合成 id 必须**确定性**（否则前端 rowKey 每次变）。

    ⚠️ 约定：`uuid5(NAMESPACE_DNS, f"lineage-root:streams:{stream_id}")`。
    """
    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    r1 = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    r2 = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r1.json()["root"]["lineage_id"] == r2.json()["root"]["lineage_id"]
    expected = uuid.uuid5(
        uuid.NAMESPACE_DNS, f"lineage-root:streams:{stream.stream_id}"
    )
    assert r1.json()["root"]["lineage_id"] == str(expected)


async def test_synthetic_root_has_same_shape_as_real_root(
    strict_client,
    db_session,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ **同形，不是最小集** —— 合成 root 的字段集 == 真实 root 的字段集。

    真实 root = `_serialize(某条真实血缘行)` ⇒ 拿它当基准 ⇒ 将来响应字段变了
    （加了/删了字段）这条测试会红。
    """
    from app.api.v1.lineage import _serialize

    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    real_row = DataLineage(
        record_type="PipingResult",
        record_id=uuid.uuid4(),
        source="CALC",
        source_ref_type="Stream",
        source_ref_id=stream.stream_id,
        change_summary="真实行",
        occurred_at=datetime.now(UTC),
    )
    db_session.add(real_row)
    await db_session.commit()
    await db_session.refresh(real_row)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    synthetic = r.json()["root"]
    real = _serialize(real_row)

    assert set(synthetic.keys()) == set(real.keys()), (
        f"合成 root 与真实 root 字段集不同：{set(synthetic.keys())} != {set(real.keys())}"
    )
    # 基准本身也要钉住（10 个字段）
    assert set(real.keys()) == {
        "lineage_id",
        "record_type",
        "record_id",
        "parent_lineage_id",
        "source",
        "source_ref_type",
        "source_ref_id",
        "actor_user_id",
        "change_summary",
        "occurred_at",
    }


async def test_synthetic_root_is_not_a_real_db_row(
    strict_client,
    db_session,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """⚠️ 文档化「这是**合成**的」—— `data_lineage` 表里**没有**这一行。"""
    from sqlalchemy import select

    project = await make_project()
    await grant_project(designer_user_id, project.project_id, username="lineage-src")
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    root_id = uuid.UUID(r.json()["root"]["lineage_id"])

    found = (
        await db_session.execute(
            select(DataLineage).where(DataLineage.lineage_id == root_id)
        )
    ).scalar_one_or_none()
    assert found is None, "合成 root 在 data_lineage 里不该有对应行"


# ---------------------------------------------------------------------------
# 3. 守卫不退化（跨项目 ⇒ 404，与「不存在」同形）
# ---------------------------------------------------------------------------


async def test_cross_project_stream_graph_is_404(
    strict_client,
    make_project,
    make_stream,
    make_source_ref_lineage,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """跨项目 ⇒ **404**（哪怕这条物流**确实有**下游血缘行）。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(designer_user_id, project_a.project_id, username="lineage-src")
    stream = await make_stream(project_b)
    await make_source_ref_lineage(stream)

    r = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_missing_and_cross_project_are_identical(
    strict_client,
    make_project,
    make_stream,
    grant_project,
    designer_user_id,
    designer_headers,
):
    """无权 ≡ 不存在 ⇒ **逐字同形** ⇒ 枚举不出某个 UUID 是否存在。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(designer_user_id, project_a.project_id, username="lineage-src")
    stream = await make_stream(project_b)

    r_missing = await strict_client.get(
        f"/api/v1/lineage/streams/{uuid.uuid4()}/graph", headers=designer_headers
    )
    r_forbidden = await strict_client.get(
        f"/api/v1/lineage/streams/{stream.stream_id}/graph", headers=designer_headers
    )
    assert r_missing.status_code == r_forbidden.status_code == 404
    assert r_missing.json()["message"] == r_forbidden.json()["message"]


# ---------------------------------------------------------------------------
# 4. 注册表完整 + 未知类型 fail-closed
# ---------------------------------------------------------------------------


def test_registry_covers_every_writable_record_type():
    """⚠️ **镜像测试**：所有能写出血缘行的类型都在守卫注册表里。

    写入方写的是 `record.__class__.__name__` ⇒ 注册表的键**必须**是类名。
    """
    from app.api.v1.lineage import LINEAGE_GUARDED_RECORD_TYPES
    from app.services.calc_lineage import RECORD_TYPE_REGISTRY

    for registry_key, model in RECORD_TYPE_REGISTRY.items():
        if not hasattr(model, "project_id"):
            # `TwoPhaseResult` 没有 project_id ⇒ **不提供**血缘查询（TODO-138）
            assert model.__name__ not in LINEAGE_GUARDED_RECORD_TYPES
            continue
        assert model.__name__ in LINEAGE_GUARDED_RECORD_TYPES, (
            f"{model.__name__}（registry 键 {registry_key}）没登记 ⇒ "
            "它的血缘行跨项目可读"
        )
        # ⚠️ registry 的键**不是**类名时（5 个），注册表里存的必须是类名
        if registry_key != model.__name__:
            assert registry_key not in LINEAGE_GUARDED_RECORD_TYPES


def test_streams_is_registered_separately():
    """`streams` 是**入口专用键**（物流在血缘行里从不作为 record_type）。"""
    from app.api.v1.lineage import LINEAGE_GUARDED_RECORD_TYPES

    model, pk = LINEAGE_GUARDED_RECORD_TYPES["streams"]
    assert model is Stream
    assert pk == "stream_id"


def test_two_phase_result_is_not_registered():
    """`TwoPhaseResult` 无 `project_id` ⇒ **不提供**血缘查询（TODO-138）。"""
    from app.api.v1.lineage import LINEAGE_GUARDED_RECORD_TYPES

    assert "TwoPhaseResult" not in LINEAGE_GUARDED_RECORD_TYPES


async def test_unknown_record_type_is_404(
    strict_client, designer_headers
):
    """未登记的 `record_type` ⇒ **404**（fail-closed，与「不存在」同形）。"""
    r = await strict_client.get(
        f"/api/v1/lineage/NotARecordType/{uuid.uuid4()}/graph", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_registry_key_cv_result_is_404(strict_client, designer_headers):
    """⚠️ `cv_result` 是 **registry 的键**，但**不是**血缘行里的 `record_type`。

    血缘行里写的是类名 `CvResult` ⇒ 用 `cv_result` 查 ⇒ 未登记 ⇒ **404**。
    """
    r = await strict_client.get(
        f"/api/v1/lineage/cv_result/{uuid.uuid4()}/graph", headers=designer_headers
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 4b. 每个已登记类型：跨项目 ⇒ 404（参数化，不写 20 条）
# ---------------------------------------------------------------------------


def _dummy_value(col):
    """给 NOT NULL 且无默认值的列造一个**类型正确**的哑值。"""
    t = col.type
    if isinstance(t, SAEnum):
        return t.enums[0]
    if isinstance(t, SAJSON):
        return {}
    if isinstance(t, SAUuid):
        return uuid.uuid4()
    if isinstance(t, Boolean):
        return True
    if isinstance(t, (Float, Numeric)):
        return 1.0
    if isinstance(t, Integer):
        return 1
    if isinstance(t, DateTime):
        return datetime.now(UTC)
    if isinstance(t, LargeBinary):
        return b"x"
    if isinstance(t, (String, Text)):
        return "TEST"
    return None


#: CHECK 约束逼出来的特例（其余列都能用类型哑值填）。
_COLUMN_OVERRIDES: dict[tuple[str, str], object] = {
    # `profile_code IN ('API','GB','CUSTOM')` + `(profile_code='CUSTOM' ⇒ approval_json 非空)`
    ("ProjectCalculationStandardProfile", "profile_code"): "API",
    ("ProjectCalculationStandardProfile", "discipline"): "PSV",
    # `circulation_type IN ('HORIZONTAL','VERTICAL')`
    ("ThermosiphonCirculationResult", "circulation_type"): "HORIZONTAL",
}


async def _make_calc_row(db: AsyncSession, model: type, project: Project):
    """造一行该类型的计算记录（**只填必填列**）⇒ 守卫能按 pk 找到它。"""
    table = model.__table__
    payload: dict = {}
    for col in table.columns:
        if col.nullable or col.default is not None or col.server_default is not None:
            continue
        override = _COLUMN_OVERRIDES.get((model.__name__, col.name))
        if override is not None:
            payload[col.name] = override
            continue
        value = _dummy_value(col)
        assert value is not None, f"{model.__name__}.{col.name} 没有哑值"
        payload[col.name] = value
    payload["project_id"] = project.project_id
    if "workspace_id" in table.columns:
        payload["workspace_id"] = project.workspace_id
    row = model(**payload)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


def _registered_calc_models() -> list[type]:
    from app.api.v1.lineage import LINEAGE_GUARDED_RECORD_TYPES

    return [
        model
        for key, (model, _pk) in LINEAGE_GUARDED_RECORD_TYPES.items()
        if key != "streams"
    ]


@pytest.mark.parametrize(
    "model", _registered_calc_models(), ids=lambda m: m.__name__
)
async def test_each_registered_type_is_guarded(
    strict_client,
    db_session,
    make_project,
    grant_project,
    designer_user_id,
    designer_headers,
    model,
):
    """每个已登记类型：**跨项目 ⇒ 404**，**本项目 ⇒ 200**（守卫没把正常路径堵死）。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(designer_user_id, project_a.project_id, username="lineage-src")

    pk_col = model.__table__.primary_key.columns[0].name

    # 项目 B（未授权）里的行 ⇒ 必须 404
    row_b = await _make_calc_row(db_session, model, project_b)
    lineage_b = DataLineage(
        record_type=model.__name__,
        record_id=getattr(row_b, pk_col),
        source="CALC",
        change_summary="跨项目",
    )
    db_session.add(lineage_b)
    await db_session.commit()

    r_forbidden = await strict_client.get(
        f"/api/v1/lineage/{model.__name__}/{getattr(row_b, pk_col)}/graph",
        headers=designer_headers,
    )
    assert r_forbidden.status_code == 404, (
        f"{model.__name__}: 跨项目没有 404 ⇒ 守卫漏了 ⇒ {r_forbidden.text}"
    )

    # 项目 A（已授权）里的同类型行 ⇒ 必须 200（对照组）
    row_a = await _make_calc_row(db_session, model, project_a)
    lineage_a = DataLineage(
        record_type=model.__name__,
        record_id=getattr(row_a, pk_col),
        source="CALC",
        change_summary="本项目",
    )
    db_session.add(lineage_a)
    await db_session.commit()

    r_allowed = await strict_client.get(
        f"/api/v1/lineage/{model.__name__}/{getattr(row_a, pk_col)}/graph",
        headers=designer_headers,
    )
    assert r_allowed.status_code == 200, (
        f"{model.__name__}: 本项目读不到 ⇒ 守卫过严 ⇒ {r_allowed.text}"
    )
