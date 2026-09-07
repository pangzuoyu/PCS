"""PipeCodeGenerator 集成测试（FMT-3）。

覆盖：基本生成/递增/并发 10/验证/无效符号/锁定。
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.pipe_code_template import (
    ProjectPipeCodeConfig,
)
from app.models.project import Project, Workspace
from app.services.exceptions import PcsError
from app.services.pipe_code_generator import PipeCodeGenerator
from app.services.stream_symbol_service import StreamSymbolService

_VALID_FMT = {
    "separator": "-",
    "segments": [
        {"key": "sym", "type": "stream_symbol", "length": 10, "position": 1},
        {"key": "seq", "type": "auto_increment", "length": 3,
         "start_value": 1, "step": 1, "padding": "zero", "position": 2},
    ],
}


async def _publish_fmt(db, project_id, fmt=None):
    """创建项目级 PUBLISHED 配置（绕过模板直建项目配置 + 走 5 态）。"""
    cfg = ProjectPipeCodeConfig(
        project_id=project_id,
        source_template_id=None,
        config_name=f"CFG-{uuid.uuid4().hex[:6]}",
        format_definition_json=fmt or _VALID_FMT,
        status="PUBLISHED",
    )
    db.add(cfg)
    await db.commit()
    return cfg


@pytest_asyncio.fixture
async def make_project(db):
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


async def _seed_project_symbol(db, project_id, symbol="FOO"):
    # 项目级符号不在公司表；直接 StreamSymbolService.add_project_symbol
    await StreamSymbolService.add_project_symbol(
        db, project_id=project_id, symbol=symbol,
        name=f"符号 {symbol}", category="PROCESS", actor=type("A", (), {"user_id": uuid.uuid4()})(),
    )


# ---------- 基本生成 ----------


async def test_generate_basic(db, make_project):
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)
    code = await PipeCodeGenerator.generate(
        db, proj.project_id, {"stream_symbol": "FOO"},
    )
    assert code == "FOO-001"


async def test_generate_increments(db, make_project):
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)
    codes = []
    for _ in range(3):
        c = await PipeCodeGenerator.generate(
            db, proj.project_id, {"stream_symbol": "FOO"},
        )
        codes.append(c)
    assert codes == ["FOO-001", "FOO-002", "FOO-003"]


async def test_generate_invalid_symbol_errors(db, make_project):
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)
    with pytest.raises(PcsError) as e:
        await PipeCodeGenerator.generate(
            db, proj.project_id, {"stream_symbol": "MISS"},
        )
    assert e.value.status == 422
    assert e.value.code == "PIPE_CODE_BAD_SYMBOL"


async def test_generate_no_published_config_errors(db, make_project):
    proj = await make_project()
    with pytest.raises(PcsError) as e:
        await PipeCodeGenerator.generate(db, proj.project_id, {})
    assert e.value.code == "PIPE_CODE_NO_CONFIG"


# ---------- 验证 ----------


async def test_validate_round_trip(db, make_project):
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)
    code = await PipeCodeGenerator.generate(
        db, proj.project_id, {"stream_symbol": "FOO"},
    )
    out = await PipeCodeGenerator.validate(db, proj.project_id, code)
    assert out.valid is True
    assert out.errors == []
    assert out.segments["sym"] == "FOO"
    assert out.segments["seq"] == "001"


async def test_validate_invalid_symbol_flags(db, make_project):
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)
    out = await PipeCodeGenerator.validate(db, proj.project_id, "BAD-001")
    assert out.valid is False
    assert any("BAD" in e for e in out.errors)


# ---------- 并发 ----------


async def test_concurrent_generate_unique(db, db_engine, make_project):
    """10 并发：每个生成器拿到独立 session；auto_increment 全部唯一。"""
    proj = await make_project()
    await _seed_project_symbol(db, proj.project_id, "FOO")
    await _publish_fmt(db, proj.project_id)

    # 10 个并发任务各自 new 一个 session（共享 db_engine in-memory SQLite）
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def worker():
        async with factory() as s:
            code = await PipeCodeGenerator.generate(
                s, proj.project_id, {"stream_symbol": "FOO"},
            )
            return code

    codes = await asyncio.gather(*[worker() for _ in range(10)])
    seqs = sorted(int(c.split("-")[1]) for c in codes)
    assert seqs == list(range(1, 11))
    assert len(set(codes)) == 10
