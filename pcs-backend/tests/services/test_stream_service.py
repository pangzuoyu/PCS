"""P3.2 SIM-4：StreamService 物流 CRUD 契约测试（spec V1.6 §3.2.3）。

设计要点：
- StreamService 是 P3.2 SIM-1 ORM + SIM-3 物性补全 + SIM-7 冲突检测的
  集成骨架（commit preview 之外的纯业务路径）
- BLOCK 冲突 → 拒绝保存（PcsError 422）
- WARN 冲突 → 保存 + warnings 元数据返回
- INFO 冲突 → 保存 + info 元数据返回
- unique (project_id, stream_name) 约束
- list 支持 case_type 过滤

测试用 in-memory SQLite（conftest 已配） + make_project 工厂建 Workspace/Project。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Stream, Workspace
from app.schemas.stream import StreamCreate, StreamUpdate
from app.services.exceptions import PcsError
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂（同 test_pipe_class_service.make_project）。"""

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


def _payload(**kw) -> dict:
    """最小有效 StreamCreate 数据。"""
    base = dict(
        stream_name="S-101",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
    )
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stream_minimal(db, make_project):
    proj = await make_project()
    payload = StreamCreate(project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload())
    stream, conflicts = await StreamService.create(db, payload, actor=uuid.uuid4())
    assert stream.stream_id is not None
    assert stream.stream_name == "S-101"
    assert stream.sign_status == "DRAFT"
    assert stream.approval_depth == 1
    # 最小 payload 无冲突
    assert conflicts.has_blocks is False


@pytest.mark.asyncio
async def test_create_stream_block_conflict_raises(db, make_project):
    """BLOCK 冲突（温度 2000K 越界）→ 拒绝保存 + raise PcsError。"""
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        # temperature_k=2000 越界；但 schema 用 temp=°C → 2000°C=2273K
        **_payload(temp=2000.0),
    )
    with pytest.raises(PcsError) as exc_info:
        await StreamService.create(db, payload, actor=uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_BLOCKED"
    # 验证未落库
    from sqlalchemy import func, select
    count = (await db.execute(select(func.count()).select_from(Stream))).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_create_stream_warn_cas_not_found_saves_with_warning(db, make_project):
    """WARN 冲突（CAS 9999-99-9 不在化学库）→ 保存 + warnings 字段含 SIM-V01-NF。"""
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id,
        workspace_id=proj.workspace_id,
        **_payload(
            composition_json={"9999-99-9": 1.0},  # 不存在 CAS
        ),
    )
    stream, conflicts = await StreamService.create(db, payload, actor=uuid.uuid4())
    assert stream.stream_id is not None
    assert conflicts.has_warnings is True
    assert any(c.code == "SIM-V01-NF" for c in conflicts.warnings)


@pytest.mark.asyncio
async def test_create_stream_duplicate_name_raises(db, make_project):
    """同 (project, stream_name) 重复 → 422（unique 约束 + 友好错误码）。"""
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    await StreamService.create(db, payload, actor=uuid.uuid4())
    # 第二次同 stream_name
    payload2 = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    with pytest.raises(PcsError) as exc_info:
        await StreamService.create(db, payload2, actor=uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_DUPLICATE_NAME"


# ---------------------------------------------------------------------------
# get / list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stream_returns_full(db, make_project):
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    stream, _ = await StreamService.create(db, payload, actor=uuid.uuid4())
    got = await StreamService.get(db, stream.stream_id)
    assert got.stream_id == stream.stream_id
    assert got.stream_name == "S-101"


@pytest.mark.asyncio
async def test_get_stream_not_found_raises(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.get(db, uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_by_project_returns_all(db, make_project):
    proj = await make_project()
    for i in range(3):
        p = StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            **_payload(stream_name=f"S-{101 + i}"),
        )
        await StreamService.create(db, p, actor=uuid.uuid4())
    streams = await StreamService.list_by_project(db, proj.project_id)
    assert len(streams) == 3
    names = {s.stream_name for s in streams}
    assert names == {"S-101", "S-102", "S-103"}


@pytest.mark.asyncio
async def test_list_by_project_filter_case_type(db, make_project):
    """list 支持 case_type 过滤。"""
    proj = await make_project()
    # 2 NORMAL + 1 END_OF_RUN
    for i, ct in enumerate(["NORMAL", "NORMAL", "END_OF_RUN"]):
        p = StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            **_payload(stream_name=f"S-{101 + i}", case_type=ct),
        )
        await StreamService.create(db, p, actor=uuid.uuid4())
    normal = await StreamService.list_by_project(db, proj.project_id, case_type="NORMAL")
    assert len(normal) == 2
    end = await StreamService.list_by_project(db, proj.project_id, case_type="END_OF_RUN")
    assert len(end) == 1


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_stream_partial(db, make_project):
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    stream, _ = await StreamService.create(db, payload, actor=uuid.uuid4())
    upd = StreamUpdate(temp=120.0, description="updated")
    updated, _ = await StreamService.update(db, stream.stream_id, upd, actor=uuid.uuid4())
    assert updated.temp == 120.0
    assert updated.description == "updated"
    # 其他字段不变
    assert updated.stream_name == "S-101"


@pytest.mark.asyncio
async def test_update_stream_block_conflict_raises(db, make_project):
    """update 触发 BLOCK 冲突 → 不保存 + 422。"""
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    stream, _ = await StreamService.create(db, payload, actor=uuid.uuid4())
    upd = StreamUpdate(temp=2000.0)  # 越界
    with pytest.raises(PcsError) as exc_info:
        await StreamService.update(db, stream.stream_id, upd, actor=uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_BLOCKED"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_stream_soft_or_hard(db, make_project):
    """delete 后 get 应 404。"""
    proj = await make_project()
    payload = StreamCreate(
        project_id=proj.project_id, workspace_id=proj.workspace_id, **_payload()
    )
    stream, _ = await StreamService.create(db, payload, actor=uuid.uuid4())
    await StreamService.delete(db, stream.stream_id, actor=uuid.uuid4())
    with pytest.raises(PcsError) as exc_info:
        await StreamService.get(db, stream.stream_id)
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_nonexistent_raises(db):
    with pytest.raises(PcsError) as exc_info:
        await StreamService.delete(db, uuid.uuid4(), actor=uuid.uuid4())
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"
