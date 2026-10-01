"""P7 Sprint 2 T7: UTIL 5 表 API 端点测试.

覆盖 T1/T5 关键集成 (POST + GET happy path):
1. POST /power-items 201 + UtilPowerItemResponse (annual 派生校验)
2. GET /power-items 200 + 列表过滤 project_id
3. POST /energy-summary/aggregate 201 + 聚合 totals > 0
4. GET /energy-summary 200 + business_year 过滤

设计:
- 复用 conftest.py:client + sample_user_token (DESIGNER)
- 不依赖 source_aggregator; 走 ORM INSERT 直接触发 service
- ACL 沿用 util.py require_roles (DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN)
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigEnergyConversionFactor
from app.models.project import Project, Workspace

# 6 类能源折标系数 (仿 T0 seed; 测试 setup 注入因 SQLite in-memory 不持 PG seed)
SEED_FACTORS = [
    {"energy_type": "ELECTRICITY", "toe_factor": 0.1229,
     "standard_coal_factor": 0.4040, "source": "SYNTHETIC_TEST_DATA"},
    {"energy_type": "FUEL_GAS", "toe_factor": 1.0000,
     "standard_coal_factor": 1.4286, "source": "SYNTHETIC_TEST_DATA"},
    {"energy_type": "STEAM", "toe_factor": 0.0760,
     "standard_coal_factor": 0.1086, "source": "SYNTHETIC_TEST_DATA"},
    {"energy_type": "WATER", "toe_factor": 0.0001,
     "standard_coal_factor": 0.0001, "source": "SYNTHETIC_TEST_DATA"},
    {"energy_type": "GAS", "toe_factor": 0.8500,
     "standard_coal_factor": 1.2143, "source": "SYNTHETIC_TEST_DATA"},
    {"energy_type": "LOW_TEMP_HEAT", "toe_factor": 0.0341,
     "standard_coal_factor": 0.0487, "source": "SYNTHETIC_TEST_DATA"},
]


@pytest_asyncio.fixture
async def pws_with_config_factors(db_session: AsyncSession):
    """最小 PWS + 6 类 ConfigEnergy折标系数 (因 SQLite 测试库不持 PG seed)."""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入折标系数
    for f in SEED_FACTORS:
        db_session.add(ConfigEnergyConversionFactor(**f))

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
    db_session.add_all([ws, proj])
    await db_session.commit()

    return {"project_id": project_id, "workspace_id": workspace_id}


# ---------------------------------------------------------------------------
# T1 /power-items
# ---------------------------------------------------------------------------


async def test_api_create_power_item_201_with_derived_annual(
    client, sample_user_token, pws_with_config_factors
):
    """POST /power-items 201 + annual_consumption_kwh 派生 (motor × hours × load)."""
    pws = pws_with_config_factors
    r = await client.post(
        "/api/v1/util/power-items",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "project_id": str(pws["project_id"]),
            "workspace_id": str(pws["workspace_id"]),
            "equipment_tag": "P-API-101",
            "motor_power_kw": 15.0,
            "operating_hours_per_year": 8000.0,
            "load_factor": 0.85,
            # 不传 annual_consumption_kwh → service 派生
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["equipment_tag"] == "P-API-101"
    # 派生 15 × 8000 × 0.85 = 102000 kWh
    assert body["annual_consumption_kwh"] == pytest.approx(102000.0, abs=1e-3)


async def test_api_list_power_items_filter_by_project(
    client, sample_user_token, pws_with_config_factors
):
    """GET /power-items 200 + 按 project_id 过滤."""
    pws = pws_with_config_factors
    # POST 2 条
    for tag in ["P-A", "P-B"]:
        r = await client.post(
            "/api/v1/util/power-items",
            headers={"Authorization": f"Bearer {sample_user_token}"},
            json={
                "project_id": str(pws["project_id"]),
                "workspace_id": str(pws["workspace_id"]),
                "equipment_tag": tag,
                "motor_power_kw": 10.0,
                "operating_hours_per_year": 8000.0,
                "load_factor": 0.8,
            },
        )
        assert r.status_code == 201

    r = await client.get(
        f"/api/v1/util/power-items?project_id={pws['project_id']}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert {r["equipment_tag"] for r in rows} == {"P-A", "P-B"}


# ---------------------------------------------------------------------------
# T5 /energy-summary/aggregate + /energy-summary
# ---------------------------------------------------------------------------


async def test_api_aggregate_energy_summary_201_with_zero_consumption(
    client, sample_user_token, pws_with_config_factors
):
    """POST /energy-summary/aggregate 201 + 零消耗聚合 (totals = 0)."""
    pws = pws_with_config_factors
    r = await client.post(
        "/api/v1/util/energy-summary/aggregate",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "project_id": str(pws["project_id"]),
            "workspace_id": str(pws["workspace_id"]),
            "business_year": 2026,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["business_year"] == 2026
    assert body["source"] == "CALCULATION"
    # 无 T1/T2/T3 消耗 → 各项 0
    assert body["total_toe"] == pytest.approx(0.0, abs=1e-3)
    assert body["total_standard_coal_kg"] == pytest.approx(0.0, abs=1e-3)
    assert body["annual_total_energy"] == pytest.approx(0.0, abs=1e-3)
    assert body["tolerance_status"] == "NA"


async def test_api_list_energy_summary_filter_by_year(
    client, sample_user_token, pws_with_config_factors
):
    """GET /energy-summary 200 + business_year 过滤."""
    pws = pws_with_config_factors
    # 聚合 2 个年度
    for year in [2026, 2027]:
        r = await client.post(
            "/api/v1/util/energy-summary/aggregate",
            headers={"Authorization": f"Bearer {sample_user_token}"},
            json={
                "project_id": str(pws["project_id"]),
                "workspace_id": str(pws["workspace_id"]),
                "business_year": year,
            },
        )
        assert r.status_code == 201

    # 不带 year → 全部
    r_all = await client.get(
        f"/api/v1/util/energy-summary?project_id={pws['project_id']}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2

    # 带 year=2026 → 仅 1 条
    r_2026 = await client.get(
        f"/api/v1/util/energy-summary?project_id={pws['project_id']}&business_year=2026",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r_2026.status_code == 200
    assert len(r_2026.json()) == 1
    assert r_2026.json()[0]["business_year"] == 2026