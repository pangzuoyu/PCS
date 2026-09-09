"""P3.x SIM-15: sim_unit_op_results + 6 专用结果表 测试。

spec §5.5 + audit V2.0 E-1：
- 主表 sim_unit_op_results 公共字段
- 6 类专用表：SimReactorResult/SimCstrResult/SimCompressorResult/SimSplitterResult/SimStcaResult/SimCalculatorResult
- FK：主表 → sim_imports（CASCADE）；专用表 → 主表（CASCADE）
- 唯一约束 (import_id, unit_uid)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.project import Project, Workspace
from app.models.sim_import import SimImport, SimImportStatus, SimImportType
from app.models.sim_unit_op import (
    SimCalculatorResult,
    SimCompressorResult,
    SimCstrResult,
    SimReactorResult,
    SimSplitterResult,
    SimStcaResult,
    SimUnitOpResult,
)


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


@pytest_asyncio.fixture
async def make_sim_import(db, make_project):
    async def _make() -> SimImport:
        proj = await make_project()
        now = datetime.now(UTC)
        sim_import = SimImport(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            import_type=SimImportType.PROII,
            status=SimImportStatus.PREVIEW,
            source_file_name="sample.inp",
            convergence_status="CONVERGED",
            banner_version="V8.5",
            preview_streams_json={"streams": []},
            warnings_json=[],
            created_by=uuid.uuid4(),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db.add(sim_import)
        await db.commit()
        return sim_import

    return _make


@pytest.mark.asyncio
async def test_sim_unit_op_main_persist(db, make_sim_import):
    """主表：13 类单元公共字段可写入。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id,
        unit_uid="R101",
        unit_type="REACTOR",
        convergence_status="CONVERGED",
        iterations=15,
        raw_summary_json={"feeds": ["FEED", "CAT"]},
        feed_streams_json=["FEED", "CAT"],
        product_streams_json=["PROD"],
    )
    db.add(unit)
    await db.commit()
    stmt = select(SimUnitOpResult).where(SimUnitOpResult.unit_op_id == unit.unit_op_id)
    loaded = (await db.execute(stmt)).scalar_one()
    assert loaded.unit_uid == "R101"
    assert loaded.unit_type == "REACTOR"
    assert loaded.iterations == 15
    assert loaded.raw_summary_json == {"feeds": ["FEED", "CAT"]}


@pytest.mark.asyncio
async def test_unique_constraint_on_import_uid(db, make_sim_import):
    """(import_id, unit_uid) UNIQUE：同一 import 内 unit_uid 不可重复。"""
    from app.models.sim_unit_op import SimUnitOpResult

    sim_import = await make_sim_import()
    db.add(SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="R101",
        unit_type="REACTOR", raw_summary_json={},
        feed_streams_json=[], product_streams_json=[],
    ))
    await db.commit()
    db.add(SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="R101",
        unit_type="REACTOR", raw_summary_json={},
        feed_streams_json=[], product_streams_json=[],
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_sim_reactor_result_persist(db, make_sim_import):
    """SimReactorResult：转换率/操作模式/RXSET。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="R101",
        unit_type="REACTOR", convergence_status="CONVERGED", iterations=15,
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    reactor = SimReactorResult(
        unit_op_id=unit.unit_op_id,
        operation_mode="ADIABATIC",
        rxset_id="DMCSET",
        reactions_count=4,
        conversions_json=[{"reaction_id": "RX1", "conversion": 0.95}],
    )
    db.add(reactor)
    await db.commit()
    assert reactor.unit_op_id == unit.unit_op_id


@pytest.mark.asyncio
async def test_sim_cstr_result_persist(db, make_sim_import):
    """SimCstrResult：停留时间/体积/出口温度。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="CSTR01",
        unit_type="REACTOR", convergence_status="CONVERGED",
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    cstr = SimCstrResult(
        unit_op_id=unit.unit_op_id,
        residence_time_min=15.0,
        volume_m3=2.5,
        outlet_temperature_k=350.0,
    )
    db.add(cstr)
    await db.commit()
    assert cstr.residence_time_min == 15.0


@pytest.mark.asyncio
async def test_sim_compressor_result_persist(db, make_sim_import):
    """SimCompressorResult：出口压力/功/效率。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="C1",
        unit_type="COMPRESSOR", convergence_status="CONVERGED", iterations=8,
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    comp = SimCompressorResult(
        unit_op_id=unit.unit_op_id,
        outlet_pressure_kpa=3610.0,
        polytropic_exponent=1.3,
        work_kw=125.5,
        efficiency=0.78,
    )
    db.add(comp)
    await db.commit()
    assert comp.efficiency == 0.78


@pytest.mark.asyncio
async def test_sim_splitter_result_persist(db, make_sim_import):
    """SimSplitterResult：分流出口列表。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="SP1",
        unit_type="SPLITTER", convergence_status="CONVERGED",
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    splitter = SimSplitterResult(
        unit_op_id=unit.unit_op_id,
        outlets_json=[
            {"stream_id": "SPLIT1", "mass_flow_kg_h": 222.0, "split_ratio": 0.499},
            {"stream_id": "SPLIT2", "mass_flow_kg_h": 223.0, "split_ratio": 0.501},
        ],
    )
    db.add(splitter)
    await db.commit()
    assert len(splitter.outlets_json) == 2


@pytest.mark.asyncio
async def test_sim_stca_result_persist(db, make_sim_import):
    """SimStcaResult：顶/底产品流/回流比。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="S2_U",
        unit_type="STCA", convergence_status="CONVERGED", iterations=7,
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    stca = SimStcaResult(
        unit_op_id=unit.unit_op_id,
        ovhd_stream="VAP",
        btms_stream="CO2",
        actual_reflux_ratio=1.5,
        min_reflux_ratio=1.2,
        num_theoretical_stages=18,
    )
    db.add(stca)
    await db.commit()
    assert stca.num_theoretical_stages == 18


@pytest.mark.asyncio
async def test_sim_calculator_result_persist(db, make_sim_import):
    """SimCalculatorResult：序列流列表。"""
    sim_import = await make_sim_import()
    unit = SimUnitOpResult(
        import_id=sim_import.import_id, unit_uid="CA1",
        unit_type="CALCULATOR", convergence_status="CONVERGED", iterations=3,
        raw_summary_json={}, feed_streams_json=[], product_streams_json=[],
    )
    db.add(unit)
    await db.commit()
    calc = SimCalculatorResult(
        unit_op_id=unit.unit_op_id,
        sequence_streams_json=["FEED", "CAT", "PROD"],
    )
    db.add(calc)
    await db.commit()
    assert calc.sequence_streams_json == ["FEED", "CAT", "PROD"]


def test_sim_unit_op_table_names():
    """所有表名契约（spec §5.5）。"""
    assert SimUnitOpResult.__tablename__ == "sim_unit_op_results"
    assert SimReactorResult.__tablename__ == "sim_reactor_results"
    assert SimCstrResult.__tablename__ == "sim_cstr_results"
    assert SimCompressorResult.__tablename__ == "sim_compressor_results"
    assert SimSplitterResult.__tablename__ == "sim_splitter_results"
    assert SimStcaResult.__tablename__ == "sim_stca_results"
    assert SimCalculatorResult.__tablename__ == "sim_calculator_results"


def test_unit_op_main_fk_to_sim_imports_cascade():
    """FK 契约：sim_unit_op_results.import_id → sim_imports.import_id CASCADE。"""
    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    fks = insp.get_foreign_keys("sim_unit_op_results")
    target = [f for f in fks if f["referred_table"] == "sim_imports"]
    assert len(target) == 1
    assert target[0]["options"]["ondelete"].upper() == "CASCADE"
    eng.dispose()


def test_specialty_table_fks_cascade():
    """FK 契约：6 类专用表 → sim_unit_op_results.unit_op_id CASCADE。"""
    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    for table in (
        "sim_reactor_results",
        "sim_cstr_results",
        "sim_compressor_results",
        "sim_splitter_results",
        "sim_stca_results",
        "sim_calculator_results",
    ):
        fks = insp.get_foreign_keys(table)
        target = [f for f in fks if f["referred_table"] == "sim_unit_op_results"]
        assert len(target) == 1, f"{table}: expected 1 FK, got {len(fks)}"
        assert target[0]["options"]["ondelete"].upper() == "CASCADE", f"{table}: not CASCADE"
    eng.dispose()
