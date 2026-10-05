"""工艺气体 / 低温热 CRUD API 测试 (P7-6B 收尾).

覆盖 4 个端点:
    GET  /api/v1/util/gas-media-items
    POST /api/v1/util/gas-media-items
    GET  /api/v1/util/low-temp-heat-items
    POST /api/v1/util/low-temp-heat-items

沿用既有子表端点约定 (参照 fuel-gas-items / heat-exchange-items):
    - ACL: DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    - BLOCKER-3 P7-7+: check_project_access_or_404 (SYSTEM_ADMIN bypass)
    - annual_* 缺省 = consumption × hours (服务端派生)
    - 非法 gas_medium / 负数 → 422
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace
from app.models.util import UtilityGasMedia, UtilityLowTempHeat


@pytest.fixture
def designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='test-user', role='DESIGNER')}"
    }


@pytest.fixture
def viewer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='v', role='VIEWER')}"
    }


@pytest.fixture
async def project(db_session: AsyncSession):
    workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(workspace_id=workspace_id, workspace_type="FORMAL", name="WS")
    )
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id, workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}", project_name="气体 API 算例",
            owner_company="PCS", location="惠州", project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN", unit_system="SI",
            product_category="REFINING",
        )
    )
    await db_session.commit()
    return project_id, workspace_id


# ---------------------------------------------------------------------------
# gas-media-items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_gas_media_derives_annual(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-1", "gas_medium": "NITROGEN",
            "consumption_nm3_h": 100.0, "operating_hours_per_year": 8000.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["gas_medium"] == "NITROGEN"
    # annual 缺省派生 = 100 × 8000
    assert body["annual_consumption_nm3"] == pytest.approx(800000.0)


@pytest.mark.asyncio
async def test_create_gas_media_accepts_explicit_annual(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-2", "gas_medium": "PURIFIED_AIR",
            "consumption_nm3_h": 10.0, "operating_hours_per_year": 8000.0,
            "annual_consumption_nm3": 12345.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["annual_consumption_nm3"] == pytest.approx(12345.0)


@pytest.mark.asyncio
async def test_create_gas_media_rejects_bad_medium(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-3", "gas_medium": "UNOBTAINIUM",
            "consumption_nm3_h": 1.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_gas_media_rejects_negative(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-4", "gas_medium": "NITROGEN",
            "consumption_nm3_h": -5.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_gas_media(
    client, db_session, project, designer_headers
):
    pid, ws = project
    for i, medium in enumerate(["NITROGEN", "PURIFIED_AIR", "PROCESS_GAS"]):
        db_session.add(
            UtilityGasMedia(
                project_id=pid, workspace_id=ws, equipment_tag=f"T-{i}",
                gas_medium=medium, consumption_nm3_h=10.0,
                operating_hours_per_year=8000.0,
                annual_consumption_nm3=80000.0, source="MANUAL",
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/util/gas-media-items?project_id={pid}", headers=designer_headers
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 3
    assert {r["gas_medium"] for r in rows} == {
        "NITROGEN", "PURIFIED_AIR", "PROCESS_GAS",
    }


@pytest.mark.asyncio
async def test_gas_media_requires_designer_role(
    client, db_session, project, viewer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-5", "gas_medium": "NITROGEN",
            "consumption_nm3_h": 1.0,
        },
        headers=viewer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_gas_medium_same_tag_conflicts(
    client, db_session, project, designer_headers
):
    pid, ws = project
    payload = {
        "project_id": str(pid), "workspace_id": str(ws),
        "equipment_tag": "ASU-DUP", "gas_medium": "NITROGEN",
        "consumption_nm3_h": 1.0,
    }
    r1 = await client.post(
        "/api/v1/util/gas-media-items", json=payload, headers=designer_headers
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/util/gas-media-items", json=payload, headers=designer_headers
    )
    assert r2.status_code in (409, 422), r2.text


# ---------------------------------------------------------------------------
# low-temp-heat-items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_low_temp_heat_derives_annual(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/low-temp-heat-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "HX-LOWT-1", "heat_recovery_gj_h": 0.05,
            "operating_hours_per_year": 8000.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["annual_recovered_heat_gj"] == pytest.approx(400.0)


@pytest.mark.asyncio
async def test_create_low_temp_heat_rejects_negative(
    client, db_session, project, designer_headers
):
    pid, ws = project
    resp = await client.post(
        "/api/v1/util/low-temp-heat-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "HX-LOWT-2", "heat_recovery_gj_h": -1.0,
        },
        headers=designer_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_low_temp_heat(
    client, db_session, project, designer_headers
):
    pid, ws = project
    for i in range(2):
        db_session.add(
            UtilityLowTempHeat(
                project_id=pid, workspace_id=ws, equipment_tag=f"LT-{i}",
                heat_recovery_gj_h=0.01, operating_hours_per_year=8000.0,
                annual_recovered_heat_gj=80.0, source="MANUAL",
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/util/low-temp-heat-items?project_id={pid}",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_persisted_rows_reach_db(
    client, db_session, project, designer_headers
):
    """POST 后确实落库 (不是只返回 DTO)."""
    pid, ws = project
    await client.post(
        "/api/v1/util/gas-media-items",
        json={
            "project_id": str(pid), "workspace_id": str(ws),
            "equipment_tag": "ASU-DB", "gas_medium": "NITROGEN",
            "consumption_nm3_h": 3.0,
        },
        headers=designer_headers,
    )
    row = (
        await db_session.execute(
            select(UtilityGasMedia).where(
                UtilityGasMedia.equipment_tag == "ASU-DB"
            )
        )
    ).scalar_one()
    assert row.gas_medium == "NITROGEN"
    assert row.annual_consumption_nm3 == pytest.approx(24000.0)
