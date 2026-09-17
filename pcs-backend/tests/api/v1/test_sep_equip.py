"""P5-2-4 SEP_EQUIP API 集成测试。

端到端验证（in-memory SQLite + httpx async）：
- POST /api/v1/sep-equip/calculate 5 类型（CYCLONE / MIST_ELIMINATOR / GRAVITY / VANE / FIBER）
- record_hash 16 hex + lineage（DataLineage.source_ref_id = stream_id）
- 三步守卫（DRAFT → 403 / 不存在 → 404 / 不合法 device_type → 422）
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.calc import SepEquipResult
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage
from app.schemas.stream import StreamCreate
from app.services.stream_service import StreamService

_HASH_RE = re.compile(r"^[0-9a-f]{16}$")


# ---------------------------------------------------------------------------
# fixtures
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
            project_name="sep_equip API 测试项目",
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
            stream_name="S-SE-201",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0, press=200.0, phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.3, "106-97-8": 0.7},
        ),
        actor=uuid.uuid4(),
    )
    sp.sign_status = StreamSignStatus.CHECKED
    await db.commit()
    await db.refresh(sp)
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _calc_body(stream_id: uuid.UUID, device: str, **kw: Any) -> dict:
    base_params: dict[str, Any] = {
        "CYCLONE": dict(
            D_cylinder_m=0.5, D_exhaust_m=0.25,
            a_inlet_m=0.2, b_inlet_m=0.1,
            V_in_ms=15.0, rho_kg_m3=1.2,
            mu_pa_s=1.8e-5, rho_particle_kg_m3=1100.0,
            N_effective_turns=5.0, method="LAPPLE",
        ),
        "MIST_ELIMINATOR": dict(
            pad_type="STANDARD",
            Q_gas_m3_s=0.5, D_cylinder_m=1.0,
            rho_gas_kg_m3=1.2, mu_gas_pa_s=1.8e-5,
            liquid_load_kg_m3=0.5,
        ),
        "GRAVITY": dict(
            d_particle_m=100e-6, rho_particle_kg_m3=1100.0,
            rho_fluid_kg_m3=1.2, mu_fluid_pa_s=1.8e-5,
            height_setting_m=1.0, horizontal_velocity_ms=0.1,
        ),
        "VANE": dict(
            d_particle_m=100e-6, rho_particle_kg_m3=1100.0,
            rho_fluid_kg_m3=1.2, mu_fluid_pa_s=1.8e-5,
            height_setting_m=1.0, horizontal_velocity_ms=0.1,
        ),
        "FIBER": dict(
            d_particle_m=100e-6, rho_particle_kg_m3=1100.0,
            rho_fluid_kg_m3=1.2, mu_fluid_pa_s=1.8e-5,
            height_setting_m=1.0, horizontal_velocity_ms=0.1,
        ),
    }[device]
    base_params.update(kw)
    return {
        "source_stream_id": str(stream_id),
        "device_type": device,
        "params": base_params,
    }


# ============================================================================
# 1) 5 类型 happy path
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device,expected_keys",
    [
        ("CYCLONE", ["pressure_drop_pa"]),
        ("MIST_ELIMINATOR", ["pad_area_m2", "K_factor_ms"]),
        ("GRAVITY", ["settling_velocity_ms", "region"]),
        ("VANE", ["settling_velocity_ms", "region"]),
        ("FIBER", ["settling_velocity_ms", "region"]),
    ],
)
async def test_calculate_sep_equip_happy_path(
    client, checked_stream, designer_headers, device, expected_keys
):
    """5 类型各返 201 + record_hash + lineage + outlet DRAFT。"""
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=_calc_body(checked_stream.stream_id, device),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["calc_type"] == device
    assert _HASH_RE.match(body["record_hash"]), body["record_hash"]
    assert len(body["lineage_ids"]) >= 1
    assert body["outlet_stream_id"] is not None
    for key in expected_keys:
        assert key in body["result"]


# ============================================================================
# 2) SepEquipResult ORM 落库：input_json + output_json 双轨
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_sep_equip_result_in_db(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """SepEquipResult ORM：input_json + output_json 双轨（device_type + params/result）。"""
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=_calc_body(checked_stream.stream_id, "CYCLONE"),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    record = await db.get(SepEquipResult, uuid.UUID(body["calc_id"]))
    assert record is not None
    assert record.input_json["device_type"] == "CYCLONE"
    assert record.output_json["device_type"] == "CYCLONE"
    assert "pressure_drop_pa" in record.output_json["result"]
    assert _HASH_RE.match(record.record_hash)


# ============================================================================
# 3) lineage record_type=SepEquipResult
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_sep_equip_lineage_in_db(
    client, db: AsyncSession, checked_stream, designer_headers
):
    """DataLineage.record_type=SepEquipResult + source_ref_id=stream_id。"""
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=_calc_body(checked_stream.stream_id, "MIST_ELIMINATOR"),
        headers=designer_headers,
    )
    assert r.status_code == 201
    body = r.json()
    rows = (
        await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "SepEquipResult",
                DataLineage.record_id == uuid.UUID(body["calc_id"]),
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].source_ref_type == "Stream"
    assert rows[0].source_ref_id == checked_stream.stream_id


# ============================================================================
# 4) 三步守卫
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_sep_equip_draft_stream_403(
    client, db: AsyncSession, make_project, designer_headers
):
    """DRAFT 状态源流 → 403 STREAM_NOT_CHECKED。"""
    proj = await make_project()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name="S-DRAFT-SE",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0, press=200.0, phase="LIQUID",
            mass_flow=1000.0,
            composition_json={"74-98-6": 0.5, "106-97-8": 0.5},
        ),
        actor=uuid.uuid4(),
    )
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=_calc_body(sp.stream_id, "CYCLONE"),
        headers=designer_headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


@pytest.mark.asyncio
async def test_calculate_sep_equip_stream_not_found_404(client, designer_headers):
    """源流 UUID 不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=_calc_body(uuid.uuid4(), "CYCLONE"),
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_calculate_sep_equip_invalid_device_422(
    client, checked_stream, designer_headers
):
    """device_type 不在 5 类 → 422 SEP_EQUIP_INPUT_ERROR。"""
    body = _calc_body(checked_stream.stream_id, "CYCLONE")
    body["device_type"] = "INVALID"
    r = await client.post(
        "/api/v1/sep-equip/calculate",
        json=body,
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "SEP_EQUIP_INPUT_ERROR"