"""INT-3：端到端集成测试（V1.4 §15）。

链路：项目模板设置默认等级 + 默认管道代码模板 → 创建项目 → 自动 fork（手动模拟） →
fork 项目级管道代码配置 → 走 5 态到 PUBLISHED → 生成管道代码 → 验证 → 项目级等级查询。
"""
from __future__ import annotations

import uuid
from collections import namedtuple

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.config_domain import ProjectPipeClass, ProjectTemplate
from app.models.pipe_code_template import ProjectPipeCodeConfig
from app.models.project import Project, Workspace
from app.services.pipe_class_service import PipeClassService
from app.services.pipe_code_generator import PipeCodeGenerator
from app.services.pipe_code_template_service import PipeCodeTemplateService
from app.services.project_template_service import ProjectTemplateService
from app.services.stream_symbol_service import StreamSymbolService

_AuthUser = namedtuple("_AuthUser", ["user_id"])


@pytest.fixture
def actor() -> _AuthUser:
    return _AuthUser(user_id=uuid.uuid4())


@pytest_asyncio.fixture
async def ws(db):
    w = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(w)
    await db.flush()
    return w


@pytest_asyncio.fixture
async def make_published_company_pc(db, actor):
    """公司级等级 DRAFT → submit → approve → publish。"""

    async def _make(class_id: str, name: str):
        from app.schemas.pipe_class import PipeClassCreate

        payload = PipeClassCreate(
            class_id=class_id,
            class_name=name,
            material_standard="ASME B31.3",
            corrosion_allowance=1.6,
            design_pressure=1.0,
            design_temperature=110.0,
            dn_series_json={"min": 15, "max": 200},
            sch_series_json={"DN15": "40,80"},
            flange_class="150#",
            source="COMPANY_STD",
            version="v1",
        )
        pc = await PipeClassService.create_with_config_asset(
            db, payload=payload, actor=actor,
        )
        await PipeClassService.submit(db, pc.class_id, actor=actor)
        await PipeClassService.approve(db, pc.class_id, actor=actor)
        await PipeClassService.publish(db, pc.class_id, actor=actor)
        return pc

    return _make


async def test_e2e_template_fork_pipe_code_generate(
    db, actor, ws, make_published_company_pc,
):
    """完整链路 e2e。"""
    # 1. 公司级等级 → PUBLISHED
    await make_published_company_pc("E2E-A1", "E2E A1")

    # 2. 公司级符号 → PUBLISHED
    sym = await StreamSymbolService.create_company(
        db, data={"symbol": "P", "name": "工艺"}, actor=actor,
    )
    await StreamSymbolService.submit(db, sym.symbol_id, actor=actor)
    await StreamSymbolService.approve(db, sym.symbol_id, actor=actor)
    await StreamSymbolService.publish(db, sym.symbol_id, actor=actor)

    # 3. 公司级管道代码模板 → PUBLISHED
    fmt = {
        "separator": "-",
        "segments": [
            {"key": "unit", "type": "enum", "values": ["100", "200"],
             "length": 3, "required": True, "position": 1},
            {"key": "stream_symbol", "type": "stream_symbol",
             "length": 10, "required": True, "position": 2},
            {"key": "sequence", "type": "auto_increment",
             "length": 3, "start_value": 1, "step": 1, "padding": "zero",
             "required": True, "position": 3, "scope": "project+symbol"},
        ],
    }
    tpl = await PipeCodeTemplateService.create_company(
        db,
        data={"template_name": "E2E-STD", "format_definition_json": fmt,
              "version": "v1"},
        actor=actor,
    )
    await PipeCodeTemplateService.submit(db, tpl.template_id, actor=actor)
    await PipeCodeTemplateService.approve(db, tpl.template_id, actor=actor)
    await PipeCodeTemplateService.publish(db, tpl.template_id, actor=actor)

    # 4. 项目模板：设置默认等级 + 默认管道代码模板
    ptpl = ProjectTemplate(
        name=f"e2e-tpl-{uuid.uuid4().hex[:8]}",
        default_config_json={},
        version="v1",
        status="ACTIVE",
        pipe_code_template_id=tpl.template_id,
    )
    db.add(ptpl)
    await db.flush()
    await ProjectTemplateService.set_default_pipe_classes(
        db, ptpl.template_id, ["E2E-A1"], actor=actor,
    )

    # 5. 创建项目
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="E2E",
        owner_company="X",
        location="X",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()

    # 6. 模拟 INT-1D 自动 fork hook（service 内不挂项目 service）
    await PipeClassService.fork_to_project(
        db, project_id=proj.project_id, class_id="E2E-A1", actor=actor,
    )
    await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=tpl.template_id,
        config_name="default", actor=actor,
    )

    # 7. 发布项目级管道代码配置
    pcc = (await db.execute(
        select(ProjectPipeCodeConfig).where(
            ProjectPipeCodeConfig.project_id == proj.project_id,
            ProjectPipeCodeConfig.source_template_id == tpl.template_id,
        )
    )).scalar_one()
    await PipeCodeTemplateService.submit_project(
        db, config_id=pcc.config_id, actor=actor,
    )
    await PipeCodeTemplateService.approve_project(
        db, config_id=pcc.config_id, actor=actor,
    )
    await PipeCodeTemplateService.publish_project(
        db, config_id=pcc.config_id, actor=actor,
    )

    # 8. 生成管道代码
    code = await PipeCodeGenerator.generate(
        db, proj.project_id, {"unit": "100", "stream_symbol": "P"},
    )
    assert code == "100-P-001"

    # 9. 验证
    outcome = await PipeCodeGenerator.validate(
        db, proj.project_id, "100-P-001",
    )
    assert outcome.valid is True
    assert outcome.segments["stream_symbol"] == "P"

    # 10. 项目级等级查询
    ppc = (await db.execute(
        select(ProjectPipeClass).where(
            ProjectPipeClass.project_id == proj.project_id,
        )
    )).scalar_one()
    assert ppc.class_name == "E2E A1"
    assert ppc.snapshot_json["material_standard"] == "ASME B31.3"

    # 11. INT-1 配套验证：模板默认等级清单可读
    default_ids = await ProjectTemplateService.get_default_pipe_class_ids(
        db, ptpl.template_id,
    )
    assert default_ids == ["E2E-A1"]


async def test_e2e_concurrent_generate_unique(db, db_engine, actor, ws, make_published_company_pc):
    """INT-3 并发：5 并发同项目同符号全部唯一。"""
    await make_published_company_pc("E2E-CON", "E2E Concurrent")
    sym = await StreamSymbolService.create_company(
        db, data={"symbol": "P", "name": "工艺"}, actor=actor,
    )
    await StreamSymbolService.submit(db, sym.symbol_id, actor=actor)
    await StreamSymbolService.approve(db, sym.symbol_id, actor=actor)
    await StreamSymbolService.publish(db, sym.symbol_id, actor=actor)

    fmt = {
        "separator": "-",
        "segments": [
            {"key": "stream_symbol", "type": "stream_symbol",
             "length": 10, "required": True, "position": 1},
            {"key": "sequence", "type": "auto_increment",
             "length": 3, "start_value": 1, "step": 1, "padding": "zero",
             "required": True, "position": 2, "scope": "project+symbol"},
        ],
    }
    tpl = await PipeCodeTemplateService.create_company(
        db,
        data={"template_name": "E2E-CON", "format_definition_json": fmt,
              "version": "v1"},
        actor=actor,
    )
    await PipeCodeTemplateService.submit(db, tpl.template_id, actor=actor)
    await PipeCodeTemplateService.approve(db, tpl.template_id, actor=actor)
    await PipeCodeTemplateService.publish(db, tpl.template_id, actor=actor)

    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="E2E-CON",
        owner_company="X", location="X",
        project_type="CHEMICAL", design_phase="FEED", unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    await PipeCodeTemplateService.fork_to_project(
        db, project_id=proj.project_id, template_id=tpl.template_id,
        config_name="default", actor=actor,
    )
    pcc = (await db.execute(
        select(ProjectPipeCodeConfig).where(
            ProjectPipeCodeConfig.project_id == proj.project_id,
        )
    )).scalar_one()
    await PipeCodeTemplateService.submit_project(
        db, config_id=pcc.config_id, actor=actor,
    )
    await PipeCodeTemplateService.approve_project(
        db, config_id=pcc.config_id, actor=actor,
    )
    await PipeCodeTemplateService.publish_project(
        db, config_id=pcc.config_id, actor=actor,
    )

    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def worker():
        async with factory() as s:
            return await PipeCodeGenerator.generate(
                s, proj.project_id, {"stream_symbol": "P"},
            )

    codes = await asyncio.gather(*[worker() for _ in range(5)])
    assert len(set(codes)) == 5  # 全部唯一
    seqs = sorted(int(c.split("-")[1]) for c in codes)
    assert seqs == [1, 2, 3, 4, 5]