"""P5-2-4 sep_equip_persist service 层测试。

覆盖：
- persist_sep_equip_calculate happy path（5 类型各 1 例）
- input_json 双轨（device_type + params）
- output_json 合并（device_type + result）
- record_hash 16 hex + lineage
- create_outlet_stream(source_type=SEP_EQUIP_CALCULATED)
- check_calc_inputs 三步守卫
"""
from __future__ import annotations

import re
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import SepEquipResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage
from app.schemas.stream import StreamCreate
from app.services.exceptions import PcsError
from app.services.sep_equip import sep_equip_persist
from app.services.stream_service import StreamService

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(
            workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}"
        )
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="sep_equip 测试项目",
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
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-SE-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


def _cyclone_params() -> dict:
    return dict(
        D_cylinder_m=0.5,
        D_exhaust_m=0.25,
        a_inlet_m=0.2,
        b_inlet_m=0.1,
        V_in_ms=15.0,
        rho_kg_m3=1.2,
        mu_pa_s=1.8e-5,
        rho_particle_kg_m3=1100.0,
        N_effective_turns=5.0,
        method="LAPPLE",
    )


def _mist_eliminator_params() -> dict:
    return dict(
        pad_type="STANDARD",
        Q_gas_m3_s=0.5,
        D_cylinder_m=1.0,
        rho_gas_kg_m3=1.2,
        mu_gas_pa_s=1.8e-5,
        liquid_load_kg_m3=0.5,
    )


def _gravity_params(sep_type: str = "GRAVITY") -> dict:
    return dict(
        d_particle_m=100e-6,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
    )


# ---------------------------------------------------------------------------
# 1. 5 类型 happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_cyclone_happy_path(db, checked_stream):
    """CYCLONE 落库 + outlet 流（source_type=SEP_EQUIP_CALCULATED）。"""
    data = await sep_equip_persist.persist_sep_equip_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        device_type="CYCLONE",
        params=_cyclone_params(),
        actor=uuid.uuid4(),
    )
    assert data["calc_type"] == "CYCLONE"
    assert _HASH_RE.match(data["record_hash"])
    assert "pressure_drop_pa" in data["result"]
    assert data["outlet_stream_id"] is not None


@pytest.mark.asyncio
async def test_persist_mist_eliminator_happy_path(db, checked_stream):
    """MIST_ELIMINATOR 落库。"""
    data = await sep_equip_persist.persist_sep_equip_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        device_type="MIST_ELIMINATOR",
        params=_mist_eliminator_params(),
    )
    assert data["calc_type"] == "MIST_ELIMINATOR"
    assert "pad_area_m2" in data["result"]
    assert "K_factor_ms" in data["result"]


@pytest.mark.asyncio
async def test_persist_gravity_plain_vane_fiber(db, checked_stream):
    """GRAVITY/VANE/FIBER 三种 separator_type 共享 gravity_separator。"""
    for device in ("GRAVITY", "VANE", "FIBER"):
        data = await sep_equip_persist.persist_sep_equip_calculate(
            db,
            source_stream_id=checked_stream.stream_id,
            device_type=device,  # type: ignore[arg-type]
            params=_gravity_params(),
        )
        assert data["calc_type"] == device
        assert data["result"]["separator_type"] == {
            "GRAVITY": "PLAIN", "VANE": "VANE", "FIBER": "FIBER"
        }[device]


# ---------------------------------------------------------------------------
# 2. input_json + output_json 双轨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_input_json_dual_track(db, checked_stream):
    """input_json 含 device_type + params；output_json 含 device_type + result。"""
    data = await sep_equip_persist.persist_sep_equip_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        device_type="CYCLONE",
        params=_cyclone_params(),
    )
    record = await db.get(SepEquipResult, data["calc_id"])
    assert record is not None
    assert record.input_json["device_type"] == "CYCLONE"
    assert record.input_json["params"]["D_cylinder_m"] == 0.5
    assert record.output_json["device_type"] == "CYCLONE"
    assert "pressure_drop_pa" in record.output_json["result"]


# ---------------------------------------------------------------------------
# 3. lineage 记录
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_lineage_recorded(db, checked_stream):
    """DataLineage.record_type=SepEquipResult + source_ref_id=stream_id。"""
    data = await sep_equip_persist.persist_sep_equip_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        device_type="CYCLONE",
        params=_cyclone_params(),
    )
    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "SepEquipResult",
                DataLineage.record_id == data["calc_id"],
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].source_ref_type == "Stream"
    assert rows[0].source_ref_id == checked_stream.stream_id


# ---------------------------------------------------------------------------
# 4. outlet_stream SEP_EQUIP_CALCULATED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_outlet_stream_sep_equip_calculated(db, checked_stream):
    """create_outlet_stream(source_type='SEP_EQUIP_CALCULATED') DRAFT 出口流。"""
    data = await sep_equip_persist.persist_sep_equip_calculate(
        db,
        source_stream_id=checked_stream.stream_id,
        device_type="MIST_ELIMINATOR",
        params=_mist_eliminator_params(),
    )
    outlet = await db.get(Stream, data["outlet_stream_id"])
    assert outlet is not None
    assert outlet.source_type == "SEP_EQUIP_CALCULATED"
    assert outlet.sign_status == StreamSignStatus.DRAFT
    assert outlet.upstream_equipment_type == "SEP_EQUIP"
    assert outlet.stream_properties_json["_calc_type"] == "SEP_EQUIP"


# ---------------------------------------------------------------------------
# 5. 三步守卫
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_draft_stream_rejected(db, make_project):
    """DRAFT 状态源流 → 403 STREAM_NOT_CHECKED。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-DRAFT",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0, press=200.0, phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.5, "106-97-8": 0.5},
        ),
        actor=uuid.uuid4(),
    )
    with pytest.raises(PcsError) as exc_info:
        await sep_equip_persist.persist_sep_equip_calculate(
            db,
            source_stream_id=sp.stream_id,
            device_type="CYCLONE",
            params=_cyclone_params(),
        )
    assert exc_info.value.status == 403


@pytest.mark.asyncio
async def test_persist_nonexistent_stream_404(db):
    """源流 UUID 不存在 → 404。"""
    with pytest.raises(PcsError) as exc_info:
        await sep_equip_persist.persist_sep_equip_calculate(
            db,
            source_stream_id=uuid.uuid4(),
            device_type="CYCLONE",
            params=_cyclone_params(),
        )
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_persist_invalid_device_type_422(db, checked_stream):
    """device_type 不在 5 类 → 422 SEP_EQUIP_INPUT_ERROR。"""
    with pytest.raises(PcsError) as exc_info:
        await sep_equip_persist.persist_sep_equip_calculate(
            db,
            source_stream_id=checked_stream.stream_id,
            device_type="INVALID",  # type: ignore[arg-type]
            params={},
        )
    assert exc_info.value.status == 422