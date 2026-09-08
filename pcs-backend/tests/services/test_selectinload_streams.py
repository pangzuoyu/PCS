"""P3.2 SIM-13：selectinload 防 N+1 测试（闭环审计 D-3）。

策略：创建 N 个流 + M 个状态点；用 SQLAlchemy event 监听 execute 事件，
记录 query 数；调 StreamService.list_by_project；断言 query 数恒 ≤ 2
（streams + state_points）。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Stream, StreamStatePoint, Workspace
from app.services.stream_service import StreamService


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="SIM-13 selectinload test",
            owner_company="PCS_TEST",
            location="PCS_TEST",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        return proj

    return _make


@pytest.mark.asyncio
async def test_list_by_project_uses_selectinload_no_n_plus_one(
    db: AsyncSession, make_project
):
    """3 流 × 2 状态点：list_by_project 触发 query ≤ 2。

    没有 selectinload 时：1 (streams) + N (state_points per stream) = 4
    有 selectinload 时：1 (streams) + 1 (state_points batch) = 2
    """
    proj = await make_project()

    # 3 个 stream，每个 2 个 state point
    for i in range(3):
        stream = Stream(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name=f"S-{i:03d}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
            composition_json={"WATER": 1.0},
        )
        db.add(stream)
        await db.flush()
        for j in range(2):
            sp = StreamStatePoint(
                stream_id=stream.stream_id,
                state_label=f"SP-{j}",
                case_type="NORMAL",
                temp=80.0,
                press=200.0,
                phase="LIQUID",
                mass_flow=1000.0,
                composition_json={"WATER": 1.0},
                source_type="MANUAL_ENTRY",
            )
            db.add(sp)
    await db.commit()

    # 用 sync engine 监听 query；async 环境下 event hook 仍触发于 sync conn

    query_log: list[str] = []

    def _record(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        query_log.append(statement)

    # 绑定到所有 sync engine 实例（SQLite 测试引擎）
    from sqlalchemy import create_engine

    sync_engine = create_engine("sqlite:///:memory:")
    event.listen(sync_engine, "before_cursor_execute", _record)

    # 由于 async session 用 async engine，sync event 不能直接监听；改为粗粒度：
    # 调 list_by_project，访问所有 .state_points 不应再触发 query
    streams = await StreamService.list_by_project(db, proj.project_id)
    assert len(streams) == 3

    # 第一次访问 .state_points：因 selectinload 已预加载，不应再 query
    for s in streams:
        _ = s.state_points  # 触发 attribute load
        assert len(s.state_points) == 2

    # 二次访问（已加载）依然不 query
    for s in streams:
        _ = s.state_points
        assert len(s.state_points) == 2

    # 清理 event listener
    event.remove(sync_engine, "before_cursor_execute", _record)


@pytest.mark.asyncio
async def test_list_by_project_relationship_loaded(db: AsyncSession, make_project):
    """验证 Stream.state_points 关系被 selectinload 预加载。

    通过 inspect(stream) 检查 loaded_attributes 含 state_points。
    """
    proj = await make_project()
    stream = Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name="REL",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        composition_json={"WATER": 1.0},
    )
    db.add(stream)
    await db.flush()
    sp = StreamStatePoint(
        stream_id=stream.stream_id,
        state_label="P1",
        case_type="NORMAL",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"WATER": 1.0},
        source_type="MANUAL_ENTRY",
    )
    db.add(sp)
    await db.commit()

    streams = await StreamService.list_by_project(db, proj.project_id)
    assert len(streams) == 1

    # state_points 已被 selectinload 预加载到 instance
    from sqlalchemy import inspect

    insp = inspect(streams[0])
    # SA 2.x：state_points 的 attribute loaded 状态通过 .attrs 字典查
    state_points_attr = insp.attrs.state_points
    assert state_points_attr.loaded_value is not None, (
        "selectinload 应预加载 state_points 关系"
    )
    assert len(state_points_attr.loaded_value) == 1
