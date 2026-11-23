"""4 条端点的**具名**响应契约（P10-H · TODO-199）。

## 为什么有本文件

TODO-199：这 4 条端点的响应在契约里**是裸 object** ⇒ ⇒ 前端拿不到任何类型
⇒ ⇒ 「形状对不对」只有**消费端**知道 ⇒ ⇒ 漂移抓不到。

⇒ ⇒ 现在它们都挂了 `response_model` ⇒ ⇒ 契约里是**具名 schema** ⇒ ⇒
本文件钉住「**响应里真的有那些字段**」。

⚠️ **载荷不许变**：加了 `response_model` 后 pydantic 会把**未赋值**的字段
补成 null ⇒ ⇒ 那会**改变现有载荷** ⇒ ⇒ 因此这 4 条都带
`response_model_exclude_unset=True` ⇒ ⇒ **只保留端点真的产出的键**
⇒ ⇒ 本文件也钉住「**不多不少**」（物性袋里没填的字段**不许**冒出来）。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, StreamStatePoint, Workspace

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="契约形状测试",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


async def _make_stream(db: AsyncSession, project: Project) -> Stream:
    stream = Stream(
        stream_name=f"S-{uuid.uuid4().hex[:6]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        project_id=project.project_id,
        workspace_id=project.workspace_id,
        phase="LIQUID",
        temp=25.0,
        press=0.5,
        mass_flow=1000.0,
        sign_status="DRAFT",
        approval_depth=1,
        record_hash="0" * 16,
        user_provided_properties_json={"mw": 100.0, "tc_k": 600.0},
        calculated_properties_json={"mw": 101.0},
        effective_properties_json={"mw": 100.0},
        conflict_resolutions_json={},
    )
    db.add(stream)
    await db.commit()
    return stream


# ---------------------------------------------------------------------------
# ① 状态点列表：具名 `StreamStatePointResponse`
# ---------------------------------------------------------------------------


async def test_state_point_list_has_the_named_fields(
    client, db: AsyncSession, make_project, designer_headers
):
    """⚠️ **状态点响应要有具名字段**（此前契约是裸 object ⇒ ⇒ 前端零类型）。"""
    project = await make_project()
    stream = await _make_stream(db, project)
    sp = StreamStatePoint(
        stream_id=stream.stream_id,
        state_label="设计工况",
        case_type="NORMAL",
        temp=25.0,
        press=0.5,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={},
        source_type="MANUAL_ENTRY",
        record_hash="0" * 16,
    )
    db.add(sp)
    await db.commit()

    r = await client.get(
        f"/api/v1/streams/{stream.stream_id}/state-points", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    row = body[0]
    for key in (
        "state_point_id",
        "stream_id",
        "state_label",
        "case_type",
        "temp",
        "press",
        "phase",
        "mass_flow",
        "composition_json",
        "source_type",
        "record_hash",
        "created_at",
    ):
        assert key in row, f"状态点响应少了 {key}（契约的 StreamStatePointResponse 要求它）"
    assert row["state_label"] == "设计工况"


# ---------------------------------------------------------------------------
# ② 物性：具名 `StreamPropertiesResponse`（且**不多**）
# ---------------------------------------------------------------------------


async def test_properties_response_keeps_exactly_the_produced_keys(
    client, db: AsyncSession, make_project, designer_headers
):
    """⚠️ **载荷不许多出 null 字段**（`exclude_unset` 的意义）。

    ⇒ ⇒ 契约模型有 19 个字段（物性全集）⇒ ⇒ 若不 exclude_unset
    ⇒ ⇒ 响应里会冒出一堆 `null` ⇒ ⇒ 那**改变了现有载荷**。
    """
    project = await make_project()
    stream = await _make_stream(db, project)

    r = await client.get(
        f"/api/v1/streams/{stream.stream_id}/properties", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {
        "stream_id",
        "user_provided",
        "calculated",
        "effective",
        "conflict_resolutions",
    }
    # ⇒ ⇒ 袋里的键也只保留**真的填了的**
    assert body["user_provided"] == {"mw": 100.0, "tc_k": 600.0}


# ---------------------------------------------------------------------------
# ③ 物性估算：具名 `StreamPropertiesEstimateResponse`
# ---------------------------------------------------------------------------


async def test_properties_estimate_response_is_results_shaped(
    client, db: AsyncSession, make_project, designer_headers
):
    """⚠️ **估算响应是 `{results: [...]}`**（此前 mock 返 `{estimated: 1}` ⇒ 与真后端不同形）。"""
    project = await make_project()
    stream = await _make_stream(db, project)

    r = await client.post(
        f"/api/v1/streams/{stream.stream_id}/properties/estimate",
        json={"cas_list": []},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"results"}
    assert body["results"] == []


# ---------------------------------------------------------------------------
# ④ 送审：具名 `StreamTransitionResponse`
# ---------------------------------------------------------------------------


async def test_submit_response_has_the_named_fields(
    client, db: AsyncSession, make_project, designer_headers
):
    """⚠️ **送审响应要有具名字段**（此前是裸 object）。"""
    project = await make_project()
    stream = await _make_stream(db, project)

    r = await client.post(
        f"/api/v1/streams/{stream.stream_id}/submit", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("stream_id", "sign_status", "approval_step"):
        assert key in body, f"送审响应少了 {key}（契约的 StreamTransitionResponse 要求它）"
    assert body["stream_id"] == str(stream.stream_id)
