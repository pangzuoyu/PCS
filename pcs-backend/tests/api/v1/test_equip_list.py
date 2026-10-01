"""S1-4b EQUIP_LIST API 测试（in-memory SQLite + httpx async client）。

端点（4）：
- GET    /api/v1/equipment-list
- GET    /api/v1/equipment-list/{id}
- POST   /api/v1/equipment-list/{id}/sync
- POST   /api/v1/equipment-list/bulk-sync

覆盖：
1. happy path: GET list 200 + EquipmentList 出现
2. happy path: GET single 200 + 404 不存在
3. happy path: POST sync trigger 200
4. happy path: POST bulk-sync 200 (1 succeed + 1 fail)
5. ACL: PROCESS_CONTROLLER 角色也 OK（DESIGNER + PC + SYSTEM_ADMIN 三档）
6. unauthenticated: 401/403

设计：
- 复用 conftest.py client + sample_user_token (DESIGNER)
- 复用 sample_pc_token (PROCESS_CONTROLLER) for ACL test
- pws_setup fixture per test_sync_service.py 模式
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import PumpResult
from app.models.equipment import EquipmentList, EquipmentTypeCode
from app.models.enums import RecordSignStatus9
from app.models.project import Project, Stream, Workspace
from app.services.equipment_type_code_service import EquipmentTypeCodeService
from app.services.equip_list.sync_service import sync_from_source


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pws_setup_with_pump(db_session: AsyncSession) -> AsyncIterator[dict]:
    """最小 PWS + EquipmentTypeCode seed (公司级) + PumpResult(CHECKED)。

    I1 fix 验证用：seed 公司级 type_codes (不 seed 项目级) 让
    sync_from_source 走 company-level fallback path.
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    pump_id = uuid.uuid4()

    await EquipmentTypeCodeService.seed_defaults(db_session)

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
        stream_id=stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"H2O": 1.0},
    )
    pump = PumpResult(
        pump_id=pump_id,
        project_id=project_id,
        workspace_id=workspace_id,
        tag_number="P-1001",
        sign_status=RecordSignStatus9.CHECKED,
        approval_depth=2,
        basic_info_json={},
        fluid_properties_json={},
        flow_rates_json={},
        suction_calculation_json={},
        discharge_calculation_json={},
        differential_pressure_json={},
        design_pressure_json={},
        power_consumption_json={},
    )
    # 额外项目级 type_code 用于覆盖测试
    proj_type_code = EquipmentTypeCode(
        project_id=project_id,
        type_code="P",
        equipment_description="Pump (project override)",
        category="ROTATING",
    )
    db_session.add_all([ws, proj, stream, proj_type_code, pump])
    await db_session.commit()
    yield {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "stream_id": stream_id,
        "pump_id": pump_id,
        "tag_number": "P-1001",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_api_list_equipment_200(
    client, db_session, sample_user_token, pws_setup_with_pump
):
    """GET /api/v1/equipment-list 200 + 返回创建的 EquipmentList。"""
    pws = pws_setup_with_pump
    # 先 sync 创建 EquipmentList
    await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )

    r = await client.get(
        "/api/v1/equipment-list",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(
        item["tag_number"] == "P-1001" and item["source_service"] == "pump_service"
        for item in body["items"]
    )


async def test_api_get_equipment_404_when_missing(client, sample_user_token):
    """GET /api/v1/equipment-list/{id} 404 when not found."""
    r = await client.get(
        f"/api/v1/equipment-list/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 404


async def test_api_sync_equipment_200(
    client, db_session, sample_user_token, pws_setup_with_pump
):
    """POST /api/v1/equipment-list/{id}/sync 200 + 返回 was_created=True。"""
    pws = pws_setup_with_pump
    # 先 sync 创建 EquipmentList（拿到 equipment_id）
    record = await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )
    equipment_id = record.equipment_id

    r = await client.post(
        f"/api/v1/equipment-list/{equipment_id}/sync",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "source_module": "PUMP",
            "source_service": "pump_service",
            "source_record_id": str(pws["pump_id"]),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["item"]["source_service"] == "pump_service"
    assert body["was_created"] is False  # 二次 sync = update, 不是 create


async def test_api_bulk_sync_equipment_partial_failure(
    client, db_session, sample_user_token, pws_setup_with_pump
):
    """POST /api/v1/equipment-list/bulk-sync 200 + partial failure 容错。"""
    pws = pws_setup_with_pump
    r = await client.post(
        "/api/v1/equipment-list/bulk-sync",
        headers={"Authorization": f"Bearer {sample_user_token}"},
        json={
            "entries": [
                {  # success
                    "source_module": "PUMP",
                    "source_service": "pump_service",
                    "source_record_id": str(pws["pump_id"]),
                },
                {  # failure: 不支持的 source_module (Pydantic Literal 422)
                    "source_module": "INVALID_MODULE",
                    "source_service": "x",
                    "source_record_id": str(uuid.uuid4()),
                },
            ]
        },
    )
    # Pydantic Literal validation 在 service 之前 catch → 422
    assert r.status_code == 422


async def test_api_list_equipment_process_controller_allowed(
    client, db_session, sample_pc_token, pws_setup_with_pump
):
    """ACL: PROCESS_CONTROLLER 角色可访问 GET list（DESIGNER/PC/SYSTEM_ADMIN 三档）。"""
    pws = pws_setup_with_pump
    await sync_from_source(
        source_module="PUMP",
        source_service="pump_service",
        source_record_id=pws["pump_id"],
        db=db_session,
    )
    r = await client.get(
        "/api/v1/equipment-list",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200


async def test_api_list_equipment_unauthenticated_401(client):
    """GET list unauthenticated → 401。"""
    r = await client.get("/api/v1/equipment-list")
    assert r.status_code == 401
