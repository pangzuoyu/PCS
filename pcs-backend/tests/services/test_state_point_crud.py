"""P3.2 SIM-8：StreamStatePoint CRUD 契约测试（spec V1.6 §3.2.2 + §3.4）。

合并到 StreamService（SIM-8 计划）：
- create_state_point：SIM-9 冲突检测（SV01~SV05），BLOCK 拒绝
- list_state_points：按 case_type 排序
- get_state_point / update_state_point / delete_state_point

测试用 in-memory SQLite（conftest 已配）+ make_project 工厂建 Workspace/Project/Stream。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Stream, Workspace
from app.schemas.stream import (
    StreamCreate,
    StreamStatePointCreate,
    StreamStatePointUpdate,
)
from app.services.exceptions import PcsError
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """Workspace + Project + Stream 工厂（按 case_type NORMAL 起点）。"""

    async def _make() -> tuple[Project, Stream]:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        stream_payload = StreamCreate(
            project_id=proj.project_id,
            workspace_id=ws.workspace_id,
            stream_name="S-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
        )
        stream, _ = await StreamService.create(db, stream_payload, actor=uuid.uuid4())
        return proj, stream

    return _make


def _state_point_payload(**kw) -> dict:
    """最小有效 StreamStatePointCreate 数据。"""
    base = dict(
        state_label="设计工况",
        case_type="NORMAL",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"WATER": 1.0},
        source_type="MANUAL_ENTRY",
    )
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# create_state_point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_state_point_minimal(db, make_project):
    _proj, stream = await make_project()
    payload = StreamStatePointCreate(
        stream_id=stream.stream_id, **_state_point_payload()
    )
    sp, report = await StreamService.create_state_point(
        db, stream.stream_id, payload, actor=uuid.uuid4()
    )
    assert sp.state_point_id is not None
    assert sp.stream_id == stream.stream_id
    assert sp.state_label == "设计工况"
    assert sp.case_type == "NORMAL"
    assert report.blocks == []


@pytest.mark.asyncio
async def test_create_state_point_parent_stream_not_found_404(db):
    payload = StreamStatePointCreate(
        stream_id=uuid.uuid4(), **_state_point_payload()
    )
    with pytest.raises(PcsError) as exc_info:
        await StreamService.create_state_point(
            db, uuid.uuid4(), payload, actor=uuid.uuid4()
        )
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_create_state_point_block_composition_sum_off(db, make_project):
    """SIM-SV03 BLOCK：组成和偏差 > 1%（sum=0.5）→ 拒绝保存。"""
    _proj, stream = await make_project()
    payload = StreamStatePointCreate(
        stream_id=stream.stream_id,
        **_state_point_payload(composition_json={"WATER": 0.5}),
    )
    with pytest.raises(PcsError) as exc_info:
        await StreamService.create_state_point(
            db, stream.stream_id, payload, actor=uuid.uuid4()
        )
    assert exc_info.value.code == "SIM_STATEPOINT_BLOCKED"


@pytest.mark.asyncio
async def test_create_state_point_warn_composition_sum_within_tolerance(db, make_project):
    """SIM-SV03 WARN：组成和偏差在 (0.1%, 1%] 区间 → 落库 + 报告中含 WARN。"""
    _proj, stream = await make_project()
    payload = StreamStatePointCreate(
        stream_id=stream.stream_id,
        **_state_point_payload(composition_json={"WATER": 0.995}),
    )
    sp, report = await StreamService.create_state_point(
        db, stream.stream_id, payload, actor=uuid.uuid4()
    )
    assert sp.state_point_id is not None
    assert any(c.code == "SIM-SV03" for c in report.warnings)


@pytest.mark.asyncio
async def test_create_state_point_same_label_different_case_type_ok(db, make_project):
    """同 state_label + 不同 case_type → 允许（设计工况 + 最大工况并存）。"""
    _proj, stream = await make_project()
    payload_normal = StreamStatePointCreate(
        stream_id=stream.stream_id,
        **_state_point_payload(case_type="NORMAL"),
    )
    payload_max = StreamStatePointCreate(
        stream_id=stream.stream_id,
        **_state_point_payload(case_type="MAX", temp=120.0),
    )
    sp_n, _ = await StreamService.create_state_point(
        db, stream.stream_id, payload_normal, actor=uuid.uuid4()
    )
    sp_m, _ = await StreamService.create_state_point(
        db, stream.stream_id, payload_max, actor=uuid.uuid4()
    )
    assert sp_n.state_point_id != sp_m.state_point_id
    assert sp_n.case_type == "NORMAL"
    assert sp_m.case_type == "MAX"


# ---------------------------------------------------------------------------
# list_state_points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_state_points_returns_sorted(db, make_project):
    _proj, stream = await make_project()
    for label, ct in [
        ("最大工况", "MAX"),
        ("设计工况", "NORMAL"),
        ("最小工况", "MIN"),
        ("替代工况", "ALTERNATE"),
    ]:
        await StreamService.create_state_point(
            db,
            stream.stream_id,
            StreamStatePointCreate(
                stream_id=stream.stream_id,
                **_state_point_payload(state_label=label, case_type=ct, temp=80.0),
            ),
            actor=uuid.uuid4(),
        )
    sps = await StreamService.list_state_points(db, stream.stream_id)
    assert len(sps) == 4
    # 按 case_type 排序
    assert [sp.case_type for sp in sps] == ["ALTERNATE", "MAX", "MIN", "NORMAL"]


@pytest.mark.asyncio
async def test_list_state_points_stream_not_found_404(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.list_state_points(db, uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_state_points_empty(db, make_project):
    _proj, stream = await make_project()
    sps = await StreamService.list_state_points(db, stream.stream_id)
    assert sps == []


# ---------------------------------------------------------------------------
# get / update / delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_state_point_200(db, make_project):
    _proj, stream = await make_project()
    sp, _ = await StreamService.create_state_point(
        db,
        stream.stream_id,
        StreamStatePointCreate(stream_id=stream.stream_id, **_state_point_payload()),
        actor=uuid.uuid4(),
    )
    got = await StreamService.get_state_point(db, sp.state_point_id)
    assert got.state_point_id == sp.state_point_id
    assert got.state_label == "设计工况"


@pytest.mark.asyncio
async def test_get_state_point_not_found_404(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.get_state_point(db, uuid.uuid4())
    assert exc_info.value.code == "SIM_STATEPOINT_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_state_point_200(db, make_project):
    _proj, stream = await make_project()
    sp, _ = await StreamService.create_state_point(
        db,
        stream.stream_id,
        StreamStatePointCreate(stream_id=stream.stream_id, **_state_point_payload()),
        actor=uuid.uuid4(),
    )
    updated, _ = await StreamService.update_state_point(
        db,
        sp.state_point_id,
        StreamStatePointUpdate(state_label="调整后", temp=100.0),
        actor=uuid.uuid4(),
    )
    assert updated.state_label == "调整后"
    assert updated.temp == 100.0


@pytest.mark.asyncio
async def test_update_state_point_not_found_404(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.update_state_point(
            db,
            uuid.uuid4(),
            StreamStatePointUpdate(state_label="X"),
            actor=uuid.uuid4(),
        )
    assert exc_info.value.code == "SIM_STATEPOINT_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_state_point(db, make_project):
    _proj, stream = await make_project()
    sp, _ = await StreamService.create_state_point(
        db,
        stream.stream_id,
        StreamStatePointCreate(stream_id=stream.stream_id, **_state_point_payload()),
        actor=uuid.uuid4(),
    )
    await StreamService.delete_state_point(
        db, sp.state_point_id, actor=uuid.uuid4()
    )
    with pytest.raises(PcsError) as exc_info:
        await StreamService.get_state_point(db, sp.state_point_id)
    assert exc_info.value.code == "SIM_STATEPOINT_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_state_point_not_found_404(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.delete_state_point(
            db, uuid.uuid4(), actor=uuid.uuid4()
        )
    assert exc_info.value.code == "SIM_STATEPOINT_NOT_FOUND"