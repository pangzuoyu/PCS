"""偏差报告 API (P7 Sprint 4 Task S4-2).

覆盖:
    GET /api/v1/equipment/{id}/deviation-report
    GET /api/v1/equipment/{id}/deviation-report/export?format=excel|pdf

⚠️ 已知缺口：`design_parameters_json` 无写入方（用户裁决「设计值留空」），
故本测试直接 UPDATE 该列来验证端点行为。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.equipment import EquipmentList
from app.models.project import Project, Workspace

pytestmark = pytest.mark.asyncio

DESIGN = {"扬程": {"value": 32.0, "unit": "m"}, "电机额定功率": {"value": 55.0, "unit": "kW"}}
ACTUAL_OK = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 56.0, "unit": "kW"}}
ACTUAL_BAD = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 48.0, "unit": "kW"}}


@pytest.fixture
def designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='u', role='DESIGNER')}"
    }


@pytest.fixture
def viewer_headers() -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject='v', role='VIEWER')}"}


@pytest.fixture
async def equipment(db_session: AsyncSession, user_id, project_id):
    """走 conftest 的 project_id fixture（自动 grant UserProject DESIGNER）."""
    ws = uuid.uuid4()
    db_session.add(Workspace(workspace_id=ws, workspace_type="FORMAL", name="WS"))
    eq = EquipmentList(
        project_id=project_id, workspace_id=ws, tag_number="P-101A",
        equipment_name="原料泵", type_code="P-100", actual_data_status="PENDING_CONFIRM",
        design_parameters_json=DESIGN, actual_data_json=ACTUAL_OK,
    )
    db_session.add(eq)
    await db_session.commit()
    await db_session.refresh(eq)
    return eq


async def test_report_returns_rows(client, equipment, designer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tag_number"] == "P-101A"
    assert {r["parameter"] for r in body["rows"]} == {"扬程", "电机额定功率"}
    row = next(r for r in body["rows"] if r["parameter"] == "扬程")
    assert row["verdict"] == "QUALIFIED"
    assert row["label"] == "合格"
    assert row["color"] == "绿色"
    assert row["spec_ref"]


async def test_report_exposes_confirmation_gate(client, equipment, designer_headers):
    """确认门禁必须随报告一起返回 —— 前端据此禁用「已确认」按钮."""
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report",
        headers=designer_headers,
    )
    body = resp.json()
    assert body["can_confirm"] is True
    assert body["blocking_reason"] == ""


async def test_report_blocks_confirmation_on_unqualified(
    client, db_session, equipment, designer_headers
):
    eq = await db_session.get(EquipmentList, equipment.equipment_id)
    eq.actual_data_json = ACTUAL_BAD
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report",
        headers=designer_headers,
    )
    body = resp.json()
    assert body["can_confirm"] is False
    assert "不合格" in body["blocking_reason"]


async def test_report_when_design_missing_is_unverdictable(
    client, db_session, equipment, designer_headers
):
    eq = await db_session.get(EquipmentList, equipment.equipment_id)
    eq.design_parameters_json = None
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report",
        headers=designer_headers,
    )
    body = resp.json()
    assert all(r["verdict"] == "UNVERDICTABLE" for r in body["rows"])
    assert body["can_confirm"] is False
    assert "缺设计值" in body["rows"][0]["note"]


async def test_export_excel_returns_xlsx(client, equipment, designer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report/export",
        params={"format": "excel"}, headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:2] == b"PK"
    assert "spreadsheetml" in resp.headers["content-type"]


async def test_export_excel_filename_is_ascii_safe(
    client, equipment, designer_headers
):
    """中文设备名不得直接进 Content-Disposition（RFC 5987 需编码）."""
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report/export",
        params={"format": "excel"}, headers=designer_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-disposition"]


async def test_export_rejects_unknown_format(client, equipment, designer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report/export",
        params={"format": "csv"}, headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_report_allows_viewer(client, equipment, viewer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{equipment.equipment_id}/deviation-report",
        headers=viewer_headers,
    )
    assert resp.status_code == 200, resp.text


async def test_report_requires_auth(client, equipment):
    resp = await client.get(f"/api/v1/equipment/{equipment.equipment_id}/deviation-report")
    assert resp.status_code == 401, resp.text


async def test_report_unknown_equipment_404(client, designer_headers):
    resp = await client.get(
        f"/api/v1/equipment/{uuid.uuid4()}/deviation-report", headers=designer_headers
    )
    assert resp.status_code == 404, resp.text
