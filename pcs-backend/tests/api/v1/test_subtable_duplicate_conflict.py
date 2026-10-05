"""既有子表 POST 端点的 UNIQUE 冲突处理 (2026-10-05).

背景: `create_power_item` / `create_fuel_gas` / `create_heat_exchange` 直接
`db.add(record); await db.commit()`, UNIQUE 冲突时 `IntegrityError` 冒泡成
**500** (httpx ASGITransport 默认 raise_server_exceptions=True, 客户端看到的是
未处理异常而不是结构化错误)。

`create_gas_media_item` / `create_low_temp_heat_item` (P7-6B 收尾新增) 已用
`_commit_or_conflict()` 转 409; 本文件把同样处理补到 3 个既有端点。

UNIQUE 约束 (app/models/util.py):
    utility_power_items     (project_id, equipment_tag)
    utility_heat_exchange   (project_id, equipment_tag)
    utility_fuel_gas        (project_id, equipment_tag, operating_phase)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace


@pytest.fixture
def designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='test-user', role='DESIGNER')}"
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
            project_no=f"P-{project_id.hex[:8]}", project_name="重复 POST 算例",
            owner_company="PCS", location="惠州", project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN", unit_system="SI",
            product_category="REFINING",
        )
    )
    await db_session.commit()
    return project_id, workspace_id


# ---------------------------------------------------------------------------
# power-items — UNIQUE(project_id, equipment_tag)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_power_items_duplicate_returns_409(
    client, db_session, project, designer_headers
):
    pid, ws = project
    payload = {
        "project_id": str(pid), "workspace_id": str(ws),
        "equipment_tag": "P-DUP", "motor_power_kw": 100.0,
        "operating_hours_per_year": 8000.0, "load_factor": 1.0,
    }
    r1 = await client.post(
        "/api/v1/util/power-items", json=payload, headers=designer_headers
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/util/power-items", json=payload, headers=designer_headers
    )
    assert r2.status_code == 409, r2.text


# ---------------------------------------------------------------------------
# heat-exchange-items — UNIQUE(project_id, equipment_tag)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heat_exchange_duplicate_returns_409(
    client, db_session, project, designer_headers
):
    pid, ws = project
    payload = {
        "project_id": str(pid), "workspace_id": str(ws),
        "equipment_tag": "HX-DUP", "temperature_class": "MP",
        "pressure_level": "0_8_TO_1_2_MPA", "medium_type": "STEAM",
        "steam_pressure_mpa_gauge": 1.0, "steam_quality_pct": 99.0,
        "return_condensate_pct": 80.0, "steam_consumption_t_h": 5.0,
        "operating_hours_per_year": 8000.0,
    }
    r1 = await client.post(
        "/api/v1/util/heat-exchange-items", json=payload, headers=designer_headers
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/util/heat-exchange-items", json=payload, headers=designer_headers
    )
    assert r2.status_code == 409, r2.text


# ---------------------------------------------------------------------------
# fuel-gas-items — UNIQUE(project_id, equipment_tag, operating_phase)
# 同 tag 不同工况应各自成功 (确认 UNIQUE 键是 3 列而非 2 列)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuel_gas_duplicate_same_phase_returns_409(
    client, db_session, project, designer_headers
):
    pid, ws = project
    payload = {
        "project_id": str(pid), "workspace_id": str(ws),
        "equipment_tag": "F-DUP", "calorific_value_kcal_nm3": 8500.0,
        "consumption_nm3_h": 100.0, "operating_phase": "STEADY",
        "operating_hours_per_year": 8000.0,
    }
    r1 = await client.post(
        "/api/v1/util/fuel-gas-items", json=payload, headers=designer_headers
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/api/v1/util/fuel-gas-items", json=payload, headers=designer_headers
    )
    assert r2.status_code == 409, r2.text


@pytest.mark.asyncio
async def test_fuel_gas_different_phase_ok(
    client, db_session, project, designer_headers
):
    """UNIQUE 键含 operating_phase → 同 tag 不同工况应都成功."""
    pid, ws = project
    base = {
        "project_id": str(pid), "workspace_id": str(ws),
        "equipment_tag": "F-MULTI", "calorific_value_kcal_nm3": 8500.0,
        "consumption_nm3_h": 100.0, "operating_hours_per_year": 8000.0,
    }
    for phase in ("STEADY", "MAX"):
        r = await client.post(
            "/api/v1/util/fuel-gas-items",
            json={**base, "operating_phase": phase},
            headers=designer_headers,
        )
        assert r.status_code == 201, f"{phase}: {r.text}"
