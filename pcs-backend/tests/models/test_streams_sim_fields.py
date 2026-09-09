"""P3.x SIM-17 + SIM-18: streams 表 8 字段扩展 测试。

spec §3.2.4 + ADD-002 §3.6：
- SIM-17: simulation_status / tear_stream / estimated / stream_properties_json
- SIM-18: user_provided_properties_json / calculated_properties_json /
  effective_properties_json / conflict_resolutions_json
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.project import Project, Stream, Workspace


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
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
        await db.commit()
        return proj

    return _make


def _make_stream(proj: Project, name: str = "S-101") -> Stream:
    return Stream(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        stream_name=name,
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
    )


@pytest.mark.asyncio
async def test_stream_sim17_fields_persist(db, make_project):
    """SIM-17 4 字段可写入并读取。"""
    proj = await make_project()
    stream = _make_stream(proj)
    stream.simulation_status = "SOLVED"
    stream.tear_stream = True
    stream.estimated = False
    stream.stream_properties_json = {
        "MW": 30.5,
        "Tc": 305.4,
        "Pc": 4.88e6,
        "acentric": 0.0995,
    }
    db.add(stream)
    await db.commit()
    stmt = select(Stream).where(Stream.stream_id == stream.stream_id)
    loaded = (await db.execute(stmt)).scalar_one()
    assert loaded.simulation_status == "SOLVED"
    assert loaded.tear_stream is True
    assert loaded.estimated is False
    assert loaded.stream_properties_json["MW"] == 30.5


@pytest.mark.asyncio
async def test_stream_sim18_fields_persist(db, make_project):
    """SIM-18 4 JSONB 字段可写入并读取。"""
    proj = await make_project()
    stream = _make_stream(proj, "S-102")
    stream.user_provided_properties_json = {"MW": 30.0, "Tc": 305.0}
    stream.calculated_properties_json = {"MW": 30.5, "Tc": 305.4, "source": "Joback"}
    stream.effective_properties_json = {"MW": 30.0}  # user_provided 优先
    stream.conflict_resolutions_json = {
        "MW": {"strategy": "USER_PROVIDED", "diff_pct": 1.67},
    }
    db.add(stream)
    await db.commit()
    stmt = select(Stream).where(Stream.stream_id == stream.stream_id)
    loaded = (await db.execute(stmt)).scalar_one()
    assert loaded.user_provided_properties_json["MW"] == 30.0
    assert loaded.calculated_properties_json["source"] == "Joback"
    assert loaded.effective_properties_json["MW"] == 30.0
    assert loaded.conflict_resolutions_json["MW"]["strategy"] == "USER_PROVIDED"


def test_streams_sim17_18_columns_exist_in_db():
    """DB 契约：streams 表新增 8 列存在。"""
    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("streams")}
    must_have = {
        # SIM-17
        "simulation_status",
        "tear_stream",
        "estimated",
        "stream_properties_json",
        # SIM-18
        "user_provided_properties_json",
        "calculated_properties_json",
        "effective_properties_json",
        "conflict_resolutions_json",
    }
    missing = must_have - cols
    assert not missing, f"missing columns: {missing}"
    eng.dispose()


def test_streams_sim17_indexes_exist():
    """SIM-17 索引契约：simulation_status + estimated 上有 B-tree 索引。"""
    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    indexes = {ix["name"] for ix in insp.get_indexes("streams")}
    assert "ix_streams_simulation_status" in indexes
    assert "ix_streams_estimated" in indexes
    eng.dispose()


@pytest.mark.asyncio
async def test_stream_sim17_18_nullable_default(db, make_project):
    """向后兼容：8 字段默认 NULL（旧数据迁移无破坏）。"""
    proj = await make_project()
    stream = _make_stream(proj, "S-OLD")
    db.add(stream)
    await db.commit()
    stmt = select(Stream).where(Stream.stream_id == stream.stream_id)
    loaded = (await db.execute(stmt)).scalar_one()
    assert loaded.simulation_status is None
    assert loaded.tear_stream is None
    assert loaded.estimated is None
    assert loaded.stream_properties_json is None
    assert loaded.user_provided_properties_json is None
    assert loaded.calculated_properties_json is None
    assert loaded.effective_properties_json is None
    assert loaded.conflict_resolutions_json is None