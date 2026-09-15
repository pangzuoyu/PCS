"""P4-4-4 PUMP 链 单元/集成测试（calc + persist + outlet 复用）。

覆盖：
1. happy path：选型 + NPSHa + 运行点 + margin > 0 → PASS
2. margin < 0：NPSHa 不足 → FAIL
3. 吸入侧 LOW confidence → WARNING
4. 吸入侧 TRANSITION → WARNING
5. 偏离设计点告警：deviation > 20% → WARNING (DEVIATION_FROM_RATED)
6. overall_confidence worst-wins
7. 落库 roundtrip：calc → persist → SELECT → input_json/output_json
8. outlet_stream 复用：source_type="PUMP_CALCULATED" →
   upstream_equipment_type="PUMP" + sign_status=DRAFT
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base as SA_Base
from app.models.calc import PumpResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.services.pump.curve_service import PumpCurve, PumpCurvePoint
from app.services.pump.pump_chain_persist import persist_pump_chain_result
from app.services.pump.pump_chain_service import (
    PumpChainInput,
    calc_pump_chain,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_CENTRIFUGAL_POINTS: tuple[PumpCurvePoint, ...] = (
    PumpCurvePoint(0.005, 36.0, 0.60, 1.5),
    PumpCurvePoint(0.010, 35.0, 0.68, 2.0),
    PumpCurvePoint(0.020, 33.0, 0.78, 2.5),
    PumpCurvePoint(0.030, 30.0, 0.80, 3.2),
    PumpCurvePoint(0.040, 26.0, 0.78, 4.0),
    PumpCurvePoint(0.050, 21.0, 0.70, 5.0),
)


def _make_curve(
    rated_flow: float = 0.030,
    rated_head: float = 30.0,
    rated_eff: float = 0.80,
    points: tuple[PumpCurvePoint, ...] = _CENTRIFUGAL_POINTS,
) -> PumpCurve:
    return PumpCurve(
        pump_tag="P-1001",
        pump_type="CENTRIFUGAL",
        api610_type="OH2",
        speed_rpm=2950.0,
        points=points,
        rated_flow_m3_s=rated_flow,
        rated_head_m=rated_head,
        rated_efficiency=rated_eff,
    )


def _make_pipe_chain_inp(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    tag_number: str = "P-SUC-1",
) -> dict:
    """构造单段吸入侧管段链字典（service 层接受 PipeChainInput dataclass）。"""
    return {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "source_stream_id": source_stream_id,
        "tag_number": tag_number,
        "inlet_pressure_pa": 200_000.0,
        "inlet_temperature_K": 298.15,
        "parallel_branches": 1,
        "segments": [
            {
                "fluid_phase": "LIQUID",
                "mass_flow_kg_s": 30.0,
                "density_kg_m3": 1000.0,
                "viscosity_pa_s": 1.0e-3,
                "pipe_diameter_m": 0.10,
                "pipe_roughness_m": 4.6e-5,
                "length_m": 5.0,
                "inclination_deg": 0.0,
                "elevation_change_m": 0.0,
            }
        ],
    }


def _make_chain_input(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    *,
    flow_m3_s: float = 0.030,
    head_m: float = 30.0,
    system_pressure_pa: float = 150_000.0,
    vapor_pressure_pa: float = 5_000.0,
    curve: PumpCurve | None = None,
    elevation_change_m: float = 0.0,
) -> PumpChainInput:
    """构造 PumpChainInput（吸入侧单段水平管 + 裕度充足系统压力）。"""
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    segments = [
        PipeSegmentInput(
            fluid_phase="LIQUID",
            mass_flow_kg_s=30.0,
            density_kg_m3=1000.0,
            viscosity_pa_s=1.0e-3,
            pipe_diameter_m=0.10,
            pipe_roughness_m=4.6e-5,
            length_m=5.0,
            inclination_deg=0.0,
            elevation_change_m=elevation_change_m,
        )
    ]
    suction = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-SUC-1",
        segments=segments,
        inlet_pressure_pa=system_pressure_pa,
        inlet_temperature_K=298.15,
        parallel_branches=1,
    )
    return PumpChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-1001",
        flow_m3_s=flow_m3_s,
        head_m=head_m,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1.0e-3,
        pump_curve=curve or _make_curve(),
        vapor_pressure_pa=vapor_pressure_pa,
        system_pressure_pa=system_pressure_pa,
        suction_pipe_chain=suction,
        elevation_change_m=elevation_change_m,
    )


# ---------------------------------------------------------------------------
# 1) Happy path
# ---------------------------------------------------------------------------


def test_calc_pump_chain_happy_path():
    """happy path：选型 + NPSHa + 运行点 + margin > 0 → PASS。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = _make_chain_input(
        project_id, workspace_id, source_stream_id,
        flow_m3_s=0.030,
        head_m=30.0,
        system_pressure_pa=150_000.0,
        vapor_pressure_pa=5_000.0,
    )

    res = calc_pump_chain(inp)

    assert res.selection.pump_type == "CENTRIFUGAL"
    assert res.selection.api610_type == "OH2"
    assert res.npsha.npsha_m > 0.0
    assert res.margin_m > 0.0
    assert res.margin_pct > 0.0
    assert res.operating_point.head_m == 30.0
    assert res.operating_point.is_rated_point is True
    assert res.overall_check_result == "PASS"
    assert res.overall_check_result_reason is None


# ---------------------------------------------------------------------------
# 2) margin < 0 → FAIL
# ---------------------------------------------------------------------------


def test_calc_pump_chain_negative_margin_fails():
    """margin < 0：NPSHa 不足 → FAIL (NEGATIVE_MARGIN)。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    # system_pressure 极低 → NPSHa 极小 → margin < 0
    inp = _make_chain_input(
        project_id, workspace_id, source_stream_id,
        flow_m3_s=0.030,
        head_m=30.0,
        system_pressure_pa=10_000.0,  # 极低
        vapor_pressure_pa=5_000.0,
    )

    res = calc_pump_chain(inp)

    assert res.margin_m < 0.0
    assert res.overall_check_result == "FAIL"
    assert res.overall_check_result_reason == "NEGATIVE_MARGIN"


# ---------------------------------------------------------------------------
# 3) 吸入侧 LOW confidence → WARNING
# ---------------------------------------------------------------------------


def test_calc_pump_chain_suction_low_confidence_warning():
    """吸入侧 LOW confidence → overall WARNING（SUCTION_LOW_RE_UNCERTAINTY）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    # 极低流速 / 极小管径 → LAMINAR → chain confidence=LOW
    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    segments = [
        PipeSegmentInput(
            fluid_phase="LIQUID",
            mass_flow_kg_s=0.0785,  # Re ≈ 1000 → LAMINAR / LOW
            density_kg_m3=1000.0,
            viscosity_pa_s=1.0e-3,
            pipe_diameter_m=0.10,
            pipe_roughness_m=4.6e-5,
            length_m=5.0,
            inclination_deg=0.0,
            elevation_change_m=0.0,
        )
    ]
    suction = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-SUC-LOW",
        segments=segments,
        inlet_pressure_pa=150_000.0,
        inlet_temperature_K=298.15,
        parallel_branches=1,
    )
    inp = PumpChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-1001-LOW",
        flow_m3_s=0.030,
        head_m=30.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1.0e-3,
        pump_curve=_make_curve(),
        vapor_pressure_pa=5_000.0,
        system_pressure_pa=150_000.0,
        suction_pipe_chain=suction,
    )
    res = calc_pump_chain(inp)
    assert res.overall_check_result == "WARNING"
    assert res.overall_check_result_reason == "SUCTION_LOW_RE_UNCERTAINTY"


# ---------------------------------------------------------------------------
# 4) 吸入侧 TRANSITION → WARNING
# ---------------------------------------------------------------------------


def test_calc_pump_chain_suction_transition_warning():
    """吸入侧 TRANSITION 流态 → WARNING（SUCTION_LOW_RE_UNCERTAINTY，沿用 P4-4-2）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    # 目标 Re ≈ 3000：D=0.05，v = Re*μ/(ρ*D) = 0.06 m/s
    # Q = v*A ≈ 1.178e-4 m³/s；ṁ = ρ*Q ≈ 0.1178 kg/s → TRANSITION
    segments = [
        PipeSegmentInput(
            fluid_phase="LIQUID",
            mass_flow_kg_s=0.1178,
            density_kg_m3=1000.0,
            viscosity_pa_s=1.0e-3,
            pipe_diameter_m=0.05,
            pipe_roughness_m=4.6e-5,
            length_m=5.0,
            inclination_deg=0.0,
            elevation_change_m=0.0,
        )
    ]
    suction = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-SUC-TR",
        segments=segments,
        inlet_pressure_pa=150_000.0,
        inlet_temperature_K=298.15,
        parallel_branches=1,
    )
    inp = PumpChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-1001-TR",
        flow_m3_s=0.030,
        head_m=30.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1.0e-3,
        pump_curve=_make_curve(),
        vapor_pressure_pa=5_000.0,
        system_pressure_pa=150_000.0,
        suction_pipe_chain=suction,
    )
    res = calc_pump_chain(inp)
    assert res.overall_check_result == "WARNING"
    assert res.overall_check_result_reason == "SUCTION_LOW_RE_UNCERTAINTY"


# ---------------------------------------------------------------------------
# 5) 偏离设计点告警
# ---------------------------------------------------------------------------


def test_calc_pump_chain_deviation_from_rated_warning():
    """deviation > 20% → WARNING (DEVIATION_FROM_RATED)。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    # rated_flow=0.030；查询 Q=0.005 → |0.005-0.030|/0.030 × 100 = 83.3% > 20%
    inp = _make_chain_input(
        project_id, workspace_id, source_stream_id,
        flow_m3_s=0.005,
        head_m=30.0,
    )
    res = calc_pump_chain(inp)
    assert res.deviation_from_rated_pct > 20.0
    assert res.overall_check_result == "WARNING"
    assert res.overall_check_result_reason == "DEVIATION_FROM_RATED"


# ---------------------------------------------------------------------------
# 6) overall_confidence worst-wins
# ---------------------------------------------------------------------------


def test_calc_pump_chain_overall_confidence_worst_wins():
    """overall_confidence worst-wins：LOW > MEDIUM > HIGH。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    from app.services.pipe.pipe_chain_service import (
        PipeChainInput,
        PipeSegmentInput,
    )

    # 极小流量 → suction confidence=LOW → 整体 worst-wins = LOW
    segments = [
        PipeSegmentInput(
            fluid_phase="LIQUID",
            mass_flow_kg_s=0.0785,  # Re ≈ 1000 → LAMINAR / LOW
            density_kg_m3=1000.0,
            viscosity_pa_s=1.0e-3,
            pipe_diameter_m=0.10,
            pipe_roughness_m=4.6e-5,
            length_m=5.0,
            inclination_deg=0.0,
            elevation_change_m=0.0,
        )
    ]
    suction = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-SUC-LOW2",
        segments=segments,
        inlet_pressure_pa=150_000.0,
        inlet_temperature_K=298.15,
        parallel_branches=1,
    )
    inp = PumpChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="P-1001-W",
        flow_m3_s=0.030,
        head_m=30.0,
        fluid_density_kg_m3=1000.0,
        fluid_viscosity_pa_s=1.0e-3,
        pump_curve=_make_curve(),
        vapor_pressure_pa=5_000.0,
        system_pressure_pa=150_000.0,
        suction_pipe_chain=suction,
    )
    res = calc_pump_chain(inp)
    assert res.overall_confidence == "LOW"


# ---------------------------------------------------------------------------
# 7) 落库 roundtrip
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """in-memory SQLite 异步引擎（隔离）。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SA_Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        session.sync_session.expire_on_flush = False
        yield session


@pytest_asyncio.fixture
async def pws_setup(db_session: AsyncSession):
    """最小 Project + Workspace + Stream(CHECKED)。"""
    from app.db.session import get_db  # noqa: F401  # 触发 SQLAlchemy 装饰

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="t",
    )
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="t",
        owner_company="t",
        location="t",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=workspace_id,
    )
    stream = Stream(
        stream_id=source_stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=StreamSignStatus.CHECKED,
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"H2O": 1.0},
    )
    db_session.add_all([ws, proj, stream])
    await db_session.flush()
    return project_id, workspace_id, source_stream_id


@pytest.mark.asyncio
async def test_persist_pump_chain_roundtrip(db_session, pws_setup):
    """落库 roundtrip：calc → persist → SELECT → input_json/output_json + record_hash。"""
    project_id, workspace_id, source_stream_id = pws_setup

    inp = _make_chain_input(
        project_id, workspace_id, source_stream_id,
        flow_m3_s=0.030,
        head_m=30.0,
    )
    res = calc_pump_chain(inp)

    row, outlet = await persist_pump_chain_result(db_session, inp, res)
    await db_session.commit()

    # pump_results 单行
    saved = (
        await db_session.execute(
            select(PumpResult).where(PumpResult.pump_id == row.pump_id)
        )
    ).scalar_one()
    assert saved.input_json is not None
    assert saved.output_json is not None
    assert saved.input_json["_calc_type"] == "PUMP_CHAIN"
    assert saved.input_json["_tag_number"] == "P-1001"
    assert saved.output_json["margin_m"] > 0.0
    assert saved.output_json["overall_check_result"] in ("PASS", "WARNING", "FAIL")
    # record_hash 由 finalize_calc_record 填（非空）
    assert saved.record_hash != ""
    assert saved.tag_number == "P-1001"


@pytest.mark.asyncio
async def test_persist_pump_chain_creates_outlet_stream(db_session, pws_setup):
    """outlet_stream 复用：source_type=PUMP_CALCULATED → upstream_equipment_type=PUMP + DRAFT。"""
    project_id, workspace_id, source_stream_id = pws_setup

    inp = _make_chain_input(
        project_id, workspace_id, source_stream_id,
        flow_m3_s=0.030,
        head_m=30.0,
    )
    res = calc_pump_chain(inp)

    _, outlet = await persist_pump_chain_result(db_session, inp, res)
    await db_session.commit()

    assert outlet.source_type == "PUMP_CALCULATED"
    assert outlet.upstream_equipment_type == "PUMP"
    assert outlet.upstream_stream_id == source_stream_id
    assert outlet.sign_status == StreamSignStatus.DRAFT
    assert outlet.approval_depth == 1
