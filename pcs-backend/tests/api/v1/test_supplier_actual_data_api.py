"""供应商实际数据录入 API — 手工 UI 路径 (P7 Sprint 4 Task S4-1).

覆盖 2 个端点 (ADR-0025 设计值→实际值流转):
    GET  /api/v1/equipment/{equipment_id}/actual-data
    PUT  /api/v1/equipment/{equipment_id}/actual-data

S4-1 裁决: 录入入口是手工 UI 页面 —— 要求供应商填统一 Excel 不现实,
故无 Excel 批量导入端点。设备方逐项在页面上录入, 一次提交一整台设备的参数集。

约定 (与既有 util 子表端点一致):
    - ACL: DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    - BLOCKER-3 P7-7+: check_project_access_or_404 (SYSTEM_ADMIN bypass)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.equipment import EquipmentList
from app.models.project import Project, Workspace


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
            project_no=f"P-{project_id.hex[:8]}", project_name="供应商录入算例",
            owner_company="PCS", location="惠州", project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN", unit_system="SI",
            product_category="REFINING",
        )
    )
    await db_session.commit()
    return project_id, workspace_id


@pytest.fixture
async def equipment(db_session: AsyncSession, project):
    pid, ws = project
    eq = EquipmentList(
        project_id=pid, workspace_id=ws, tag_number="E-1001",
        equipment_name="换热器", type_code="E-100", actual_data_status="NOT_ENTERED",
    )
    db_session.add(eq)
    await db_session.commit()
    await db_session.refresh(eq)
    return eq


_ENTRIES = [
    {"name": "设计温度", "value": 102.0, "unit": "℃"},
    {"name": "设计压力", "value": 1.65, "unit": "MPa"},
]


# ---------------------------------------------------------------------------
# PUT — 录入
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_records_actual_data(
    client, db_session, equipment, designer_headers
):
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": _ENTRIES},
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["actual_data_status"] == "PENDING_CONFIRM"
    assert body["actual_data_json"] == {
        "设计温度": {"value": 102.0, "unit": "℃"},
        "设计压力": {"value": 1.65, "unit": "MPa"},
    }


@pytest.mark.asyncio
async def test_put_replaces_previous(
    client, db_session, equipment, designer_headers
):
    """二次提交整体替换 —— 页面上的"重录"不是"追加"."""
    await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": _ENTRIES}, headers=designer_headers,
    )
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": [{"name": "换热面积", "value": 32.5, "unit": "m2"}]},
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["actual_data_json"]) == {"换热面积"}


@pytest.mark.asyncio
async def test_put_rejects_non_numeric_value(
    client, equipment, designer_headers
):
    """非数值 → 422, 且带出错项的定位信息 (UI 逐项提示, 不静默丢).

    类型错误由 Pydantic schema 拦 (code=VALIDATION_ERROR) —— schema 保持
    `value: float` 是刻意的: 前端 TS 类型由此生成, 放宽成 Any 会退化成 unknown。
    语义错误 (重复名 / 空名) 才由 service 报 ACTUAL_DATA_VALIDATION。
    """
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": [{"name": "设计温度", "value": "一百多度", "unit": "℃"}]},
        headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    # loc 指到出错项 —— UI 据此高亮那一行
    assert any("value" in str(part) for part in body.get("detail", []))


@pytest.mark.asyncio
async def test_put_rejects_duplicate_name(client, equipment, designer_headers):
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={
            "entries": [
                {"name": "设计温度", "value": 100.0, "unit": "℃"},
                {"name": "设计温度", "value": 102.0, "unit": "℃"},
            ]
        },
        headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "ACTUAL_DATA_VALIDATION"


@pytest.mark.asyncio
async def test_put_rejects_empty_entries(client, equipment, designer_headers):
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": []}, headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_put_rejects_viewer(client, equipment, viewer_headers):
    """VIEWER 只读 —— 录入需写权限."""
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": _ENTRIES}, headers=viewer_headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_put_unknown_equipment_404(client, designer_headers):
    resp = await client.put(
        f"/api/v1/equipment/{uuid.uuid4()}/actual-data",
        json={"entries": _ENTRIES}, headers=designer_headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# GET — 读回
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_empty_before_entry(client, equipment, designer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["actual_data_status"] == "NOT_ENTERED"
    assert body["actual_data_json"] is None


@pytest.mark.asyncio
async def test_get_roundtrips_after_put(client, equipment, designer_headers):
    await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": _ENTRIES}, headers=designer_headers,
    )
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["actual_data_json"]) == {"设计温度", "设计压力"}


@pytest.mark.asyncio
async def test_get_requires_auth(client, equipment):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data"
    )
    assert resp.status_code == 401, resp.text
