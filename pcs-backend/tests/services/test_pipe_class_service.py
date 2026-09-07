"""PipeClassService 单元测试（Task 1.9.1 / P2-STD-001）。

覆盖：service 层 delete（已分配→409）+ list_project（fork 后列出）。
SUP-002 后改用 fork_to_project 路径构造 ProjectPipeClass 行（service.delete 通过
ProjectPipeClass.class_id 列做引用检查；旧 assign_to_project(class_id) 已弃用）。
"""
import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError

from app.models.config_domain import ProjectPipeClass
from app.models.project import Project, Workspace
from app.schemas.pipe_class import PipeClassCreate, PipeClassUpdate
from app.services.exceptions import PcsError
from app.services.pipe_class_service import PipeClassService


def _payload(class_id="A1", **kw):
    base = dict(
        class_id=class_id, class_name="管道等级 A1", material_standard="GB/T 8163",
        corrosion_allowance=1.5, design_pressure=2.5, design_temperature=200.0,
        dn_series_json={"min": 15, "max": 350},
        sch_series_json={"15": "40", "25": "40", "50": "40", "100": "40", "350": "STD"},
        flange_class="PN25", source="COMPANY_STD", version="PC-V1.0",
    )
    base.update(kw)
    return PipeClassCreate(**base)


@pytest_asyncio.fixture
async def make_project(db):
    """conftest 无 make_project → 本文件内定义（brief 注）。

    Project 必填列（app/models/project.py）：project_no / project_name /
    owner_company / location / project_type / design_phase / unit_system +
    workspace_id（NOT NULL FK，projects↔workspaces use_alter 循环），
    故先建 Workspace 再建最小 Project。
    """

    async def _make():
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


async def test_create_and_get(db):
    pc = await PipeClassService.create(db, payload=_payload())
    assert pc.status == "DRAFT"
    got = await PipeClassService.get(db, "A1")
    assert got.class_name == "管道等级 A1"


async def test_get_missing_raises_404(db):
    with pytest.raises(PcsError) as e:
        await PipeClassService.get(db, "NOPE")
    assert e.value.status == 404


async def test_create_duplicate_raises_409(db):
    await PipeClassService.create(db, payload=_payload())
    with pytest.raises(PcsError) as e:
        await PipeClassService.create(db, payload=_payload())
    assert e.value.status == 409


async def test_create_invalid_dn_range_422():
    # brief 偏差（报告有记录）：dn 校验位于 schema model_validator，构造 payload 即抛
    # pydantic ValidationError（API 层映射 422），非法数据到不了 service，故不可能是 PcsError。
    with pytest.raises(ValidationError) as e:
        _payload(dn_series_json={"min": 600, "max": 15})
    assert "dn_series_json" in str(e.value)


async def test_update_and_obsolete_one_way(db):
    await PipeClassService.create(db, payload=_payload())
    up = await PipeClassService.update(db, "A1", payload=PipeClassUpdate(
        **{**_payload().model_dump(), "design_pressure": 4.0, "status": "ACTIVE"}))
    assert up.design_pressure == 4.0 and up.status == "ACTIVE"
    dead = await PipeClassService.update(db, "A1", payload=PipeClassUpdate(
        **{**_payload().model_dump(), "status": "OBSOLETE"}))
    assert dead.status == "OBSOLETE"
    with pytest.raises(PcsError) as e:  # OBSOLETE 不可改回
        await PipeClassService.update(db, "A1", payload=PipeClassUpdate(
            **{**_payload().model_dump(), "status": "ACTIVE"}))
    assert e.value.status == 409


async def test_delete_blocked_when_assigned(db, make_project, actor):
    """fork 出的 ProjectPipeClass.class_id 引用 → delete 应抛 409（不可删，仅可作废）。

    SUP-002：原 1.9 assign_to_project(class_id) 已弃用，改走 fork_to_project 入口。
    fork 在 ProjectPipeClass.class_id 上落行，与 service.delete 的引用检查匹配。
    """
    await PipeClassService.create(db, payload=_payload())
    proj = await make_project()
    await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id="A1", actor=actor,
    )
    with pytest.raises(PcsError) as e:
        await PipeClassService.delete(db, "A1")
    assert e.value.status == 409  # 已用等级不可删除，仅可作废


async def test_list_project_returns_assignment(db, make_project, actor):
    """fork 后 list_project 应返回该行的 class_name（SUP-002 PC-4：class_id 不再是列）。"""
    await PipeClassService.create(db, payload=_payload())
    proj = await make_project()
    row = await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id="A1", actor=actor,
    )
    rows = await PipeClassService.list_project(db, proj.project_id)
    # SUP-002 PC-1：ProjectPipeClass.class_id 列已废；fork 写入 class_name（来自公司级）
    assert [r.class_name for r in rows] == ["管道等级 A1"]
    assert row.source_class_id == "A1"
    assert isinstance(row, ProjectPipeClass)
