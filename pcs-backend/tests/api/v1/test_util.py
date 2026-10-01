"""S1-5b UTIL API 测试（in-memory SQLite + httpx async client）。

端点（6）：
- GET    /api/v1/util/results
- GET    /api/v1/util/results/{id}
- POST   /api/v1/util/results
- POST   /api/v1/util/aggregate
- GET    /api/v1/util/summary
- GET    /api/v1/util/energy-consumption
- GET    /api/v1/util/water-balance

覆盖：
1. POST /results 201 + UtilResultsResponse
2. POST /aggregate 201 (PUMP result auto-aggregated to ELECTRICITY)
3. GET /summary 200 + toe_total > 0 + standard_coal_total > 0
4. GET /energy-consumption 200 + 5 energy categories filtered
5. GET /water-balance 200 + 3 water categories
6. ACL: PROCESS_CONTROLLER role OK
7. unauthenticated 401

设计：
- 复用 conftest.py client + sample_user_token (DESIGNER)
- 复用 sample_pc_token (PROCESS_CONTROLLER) for ACL test
- 手动 create UtilResults（不调 aggregate_and_save — source_aggregator 需 PUMP/HEAT 等结果 fixture）
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Workspace
from app.models.util import UtilResults
from app.services.toe_conversion_service import ToeConversionService
from app.services.util.persist_service import save_util_results


@pytest_asyncio.fixture
async def pws_setup(db_session: AsyncSession) -> AsyncIterator[dict]:
    """最小 PWS + ToeConversionFactor seed + UtilResults 实例（含 13 类消耗量）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    await ToeConversionService.seed_defaults(db_session)

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

    # 手动 create UtilResults（13 类全填）
    record = await save_util_results(
        db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        consumption_json={
            "ELECTRICITY": 10000.0,
            "STEAM_HP": 50.0,
            "STEAM_MP": 30.0,
            "STEAM_LP": 20.0,
            "CONDENSATE": 90.0,
            "COOLING_WATER": 500.0,
            "CHILLED_WATER": 200.0,
            "MAKEUP_WATER": 50.0,
            "FUEL_GAS": 10000.0,
            "NITROGEN": 10.0,
            "INSTRUMENT_AIR": 20.0,
            "PLANT_AIR": 30.0,
        },
        source="test fixture",
    )
    yield {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "util_result_id": record.util_result_id,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_api_create_util_results_201(client, sample_user_token):
    """POST /api/v1/util/results 201 + UtilResultsResponse。"""
    r = await client.post(
        "/api/v1/util/results",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "project_id": str(uuid.uuid4()),
            "workspace_id": str(uuid.uuid4()),
            "consumption_json": {"ELECTRICITY": 100.0},
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["consumption_json"]["ELECTRICITY"] == 100.0
    assert body["jsonb_deprecated"] is False


async def test_api_aggregate_util_results_201(
    client, db_session, sample_user_token, pws_setup
):
    """POST /api/v1/util/aggregate 201 + aggregation writes new UtilResults。

    因 source_aggregator 需要 PUMP/HEAT/COOL_TOWER/OPEN_CHANNEL CHECKED results，
    本测试不预先建这些，aggregator 返回空 dict → UtilResults 全 0 写入。
    """
    pws = pws_setup
    r = await client.post(
        "/api/v1/util/aggregate",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "project_id": str(pws["project_id"]),
            "workspace_id": str(pws["workspace_id"]),
            "modules": ["PUMP"],  # 限制聚合到 PUMP（HEAT/COOL/OPEN 无源数据）
        },
    )
    assert r.status_code == 201
    body = r.json()
    # PUMP 无源数据 → ELECTRICITY = 0
    assert body["consumption_json"]["ELECTRICITY"] == 0.0
    assert body["source"] == "source_aggregator"


async def test_api_get_util_summary_200(
    client, sample_user_token, pws_setup
):
    """GET /api/v1/util/summary 200 + toe_total > 0 + 13 类 by_category 完整。"""
    pws = pws_setup
    r = await client.get(
        f"/api/v1/util/summary?util_result_id={pws['util_result_id']}&year=2026",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "by_category" in body
    assert len(body["by_category"]) == 13
    assert body["toe_total"] > 0
    assert body["standard_coal_total"] > 0
    assert body["year"] == 2026


async def test_api_get_util_energy_consumption_200(
    client, sample_user_token, pws_setup
):
    """GET /api/v1/util/energy-consumption 200 + 6 energy categories filtered。

    F-P1-015 fix: 由 5 类扩展到 6 类 (含 CONDENSATE)，与 toe_total 计算口径一致
    (CONDENSATE 按 STEAM 折标).
    """
    pws = pws_setup
    r = await client.get(
        f"/api/v1/util/energy-consumption?util_result_id={pws['util_result_id']}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    # F-P1-015 fix: 6 能源类 (含 CONDENSATE)
    assert set(body["by_category"].keys()) == {
        "ELECTRICITY", "STEAM_HP", "STEAM_MP", "STEAM_LP", "FUEL_GAS", "CONDENSATE",
    }
    assert body["toe_total"] > 0


async def test_api_get_util_water_balance_200(
    client, sample_user_token, pws_setup
):
    """GET /api/v1/util/water-balance 200 + 3 water categories。"""
    pws = pws_setup
    r = await client.get(
        f"/api/v1/util/water-balance?util_result_id={pws['util_result_id']}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["by_category"].keys()) == {
        "COOLING_WATER", "CHILLED_WATER", "MAKEUP_WATER",
    }
    # 500 + 200 + 50 = 750
    assert body["total_water_t"] == 750.0


async def test_api_get_util_summary_process_controller_allowed(
    client, sample_pc_token, pws_setup
):
    """ACL: PROCESS_CONTROLLER 角色可访问 GET summary。"""
    pws = pws_setup
    r = await client.get(
        f"/api/v1/util/summary?util_result_id={pws['util_result_id']}",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200


async def test_api_list_util_results_unauthenticated_401(client):
    """GET /util/results unauthenticated → 401。"""
    r = await client.get("/api/v1/util/results")
    assert r.status_code == 401
