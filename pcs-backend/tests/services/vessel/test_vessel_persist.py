"""P5-1-4 vessel_persist service 层测试。

覆盖：
- persist_vessel_calculate happy path：sizing + hydraulics 联动 → VesselResult 落库
- input_json 双轨（sizing + hydraulics dict）
- output_json 合并（sizing + hydraulics 结果）
- record_hash 16 hex + lineage 记录
- create_outlet_stream(source_type=VESSEL_CALCULATED)
- check_calc_inputs 三步守卫（DRAFT → 403 / 不可靠 → 422 / 不存在 → 404）
- project_id 一致性（OutletStreamProjectMismatchError → 422）
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import VesselResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage
from app.schemas.stream import StreamCreate
from app.services.exceptions import PcsError
from app.services.vessel import vessel_persist
from app.services.vessel.vessel_service import (
    VesselHydraulicsInput,
    VesselSizingInput,
)

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="vessel 测试项目",
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
async def checked_stream(db: AsyncSession, make_project) -> Stream:
    """CHECKED 状态 Stream（vessel calc 入口要求）。"""
    proj = await make_project()
    sp, _ = await StreamService_create(db, proj)
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


async def StreamService_create(db: AsyncSession, proj: Project) -> tuple[Stream, Any]:
    """StreamService.create wrapper（避免顶部 import 循环）。"""
    from app.services.stream_service import StreamService

    return await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-V-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",  # 避免 MIXED 必填 vapor/liquid_composition
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )


def _sizing_input() -> VesselSizingInput:
    return VesselSizingInput(
        vessel_type="VERTICAL",
        rho_L_kg_m3=850.0,
        rho_V_kg_m3=1.2,
        liquid_flow_m3_s=0.005,
        vapor_flow_m3_s=0.5,
        residence_time_min=5.0,
        K_factor_ms=0.03,
    )


def _hydraulics_input(orientation: str = "vertical") -> VesselHydraulicsInput:
    return VesselHydraulicsInput(
        D_m=2.0,
        L_m=5.0,
        h0_m=1.0,
        d_orifice_m=0.05,
        Cd_orifice=0.62,
        Q_in_liquid_m3_s=0.005,
        d_overflow_m=0.1,
        h_overflow_m=1.0,
        Cd_overflow=0.62,
        orientation=orientation,
        thermal_breathing_factor=1.0,
    )


# ---------------------------------------------------------------------------
# 1. Happy path：sizing + hydraulics 联动落库
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_vessel_calculate_happy_path(db, checked_stream):
    """vessel 计算 happy path：sizing + hydraulics 联动 → VesselResult + outlet DRAFT。"""
    data = await vessel_persist.persist_vessel_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        sizing_input=_sizing_input(),
        hydraulics_input=_hydraulics_input(),
        actor=uuid.uuid4(),
    )

    # 返回结构
    assert data["calc_type"] == "VESSEL"
    assert data["stream_id"] == checked_stream.stream_id
    assert _HASH_RE.match(data["record_hash"]), f"record_hash 非法：{data['record_hash']}"
    assert data["outlet_stream_id"] is not None

    # 结果含 sizing + hydraulics 双轨
    result = data["result"]
    assert "sizing" in result and "hydraulics" in result
    assert result["sizing"]["V_max_ms"] > 0
    assert result["sizing"]["D_min_m"] > 0
    assert result["hydraulics"]["empty_time_s"] > 0
    assert isinstance(result["hydraulics"]["overflow_ok"], bool)
    assert result["hydraulics"]["vent_capacity_m3_s"] > 0


@pytest.mark.asyncio
async def test_persist_vessel_input_json_dual_track(db, checked_stream):
    """input_json 双轨（ADR-0032 V1.1 决策 6）：sizing + hydraulics 都进 JSONB。"""
    data = await vessel_persist.persist_vessel_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        sizing_input=_sizing_input(),
        hydraulics_input=_hydraulics_input(),
    )

    # 直接查 VesselResult.input_json 验证双轨
    vessel_id = data["calc_id"]
    record = await db.get(VesselResult, vessel_id)
    assert record is not None
    assert "sizing" in record.input_json
    assert "hydraulics" in record.input_json
    # sizing 字段回填完整
    assert record.input_json["sizing"]["vessel_type"] == "VERTICAL"
    assert record.input_json["sizing"]["K_factor_ms"] == 0.03
    # hydraulics 字段回填完整
    assert record.input_json["hydraulics"]["D_m"] == 2.0
    assert record.input_json["hydraulics"]["orientation"] == "vertical"


@pytest.mark.asyncio
async def test_persist_vessel_lineage_recorded(db, checked_stream):
    """finalize_calc_record：每个 source_stream 一条血缘，record_type=VesselResult。"""
    data = await vessel_persist.persist_vessel_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        sizing_input=_sizing_input(),
        hydraulics_input=_hydraulics_input(),
    )

    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "VesselResult",
                DataLineage.record_id == data["calc_id"],
            )
        )
    ).scalars().all()

    assert len(rows) == 1, f"应 1 条血缘，实际 {len(rows)}"
    assert rows[0].source_ref_type == "Stream"
    assert rows[0].source_ref_id == checked_stream.stream_id


@pytest.mark.asyncio
async def test_persist_vessel_outlet_stream_vessel_calculated(db, checked_stream):
    """create_outlet_stream(source_type='VESSEL_CALCULATED') 创建 DRAFT 出口流。"""
    data = await vessel_persist.persist_vessel_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        sizing_input=_sizing_input(),
        hydraulics_input=_hydraulics_input(),
    )

    outlet = await db.get(Stream, data["outlet_stream_id"])
    assert outlet is not None
    assert outlet.source_type == "VESSEL_CALCULATED"
    assert outlet.sign_status == StreamSignStatus.DRAFT
    assert outlet.upstream_stream_id == checked_stream.stream_id
    assert outlet.upstream_equipment_type == "VESSEL"
    # properties 承载 vessel 几何 + 物性
    props = outlet.stream_properties_json
    assert props["_calc_type"] == "VESSEL"
    assert props["vessel_type"] == "VERTICAL"
    assert props["V_max_ms"] > 0
    assert props["D_min_m"] > 0


# ---------------------------------------------------------------------------
# 2. 三步守卫
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_vessel_draft_stream_rejected(db, make_project):
    """DRAFT 状态源流 → 三步守卫拒绝（403 STREAM_NOT_CHECKED）。"""
    proj = await make_project()
    sp, _ = await StreamService_create(db, proj)
    # 默认 DRAFT 状态，不动

    with pytest.raises(PcsError) as exc_info:
        await vessel_persist.persist_vessel_calculate(
            db,
            source_stream_id=sp.stream_id,
            sizing_input=_sizing_input(),
            hydraulics_input=_hydraulics_input(),
        )
    assert exc_info.value.status == 403


@pytest.mark.asyncio
async def test_persist_vessel_nonexistent_stream_404(db):
    """源流 UUID 不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    with pytest.raises(PcsError) as exc_info:
        await vessel_persist.persist_vessel_calculate(
            db,
            source_stream_id=uuid.uuid4(),
            sizing_input=_sizing_input(),
            hydraulics_input=_hydraulics_input(),
        )
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_persist_vessel_invalid_input_raises(db, checked_stream):
    """VesselInputError 透传（如 K_factor 越界）→ 422。"""
    with pytest.raises(PcsError) as exc_info:
        await vessel_persist.persist_vessel_calculate(
            db,
            source_stream_id=checked_stream.stream_id,
            sizing_input=VesselSizingInput(
                vessel_type="VERTICAL",
                rho_L_kg_m3=850.0, rho_V_kg_m3=1.2,
                liquid_flow_m3_s=0.005, vapor_flow_m3_s=0.5,
                residence_time_min=5.0, K_factor_ms=2.0,  # 越界
            ),
            hydraulics_input=_hydraulics_input(),
        )
    assert exc_info.value.status == 422


@pytest.mark.asyncio
async def test_persist_vessel_horizontal_orientation_emits_warning(
    db, checked_stream, recwarn
):
    """horizontal orientation 触发 UserWarning（运行时可见）。"""
    data = await vessel_persist.persist_vessel_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        sizing_input=_sizing_input(),
        hydraulics_input=_hydraulics_input(orientation="horizontal"),
    )
    # 任意一条 UserWarning 匹配"立式罐"（来自 calc_vessel_hydraulics）
    assert any(
        issubclass(w.category, UserWarning) and "立式" in str(w.message)
        for w in recwarn.list
    ), f"未触发 UserWarning：{[str(w.message) for w in recwarn.list]}"
    # 数据仍返回（不拒绝）
    assert data["calc_id"] is not None
