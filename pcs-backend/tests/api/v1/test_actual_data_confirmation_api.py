"""核算与更新流程 API (P7 Sprint 4 Task S4-3).

覆盖:
    POST /api/v1/equipment/{id}/actual-data/confirm  (设计人提交校核)
    POST /api/v1/equipment/{id}/actual-data/check    (校核人通过/退回)

ACL 分工: 设计人确认 (DESIGNER+) / 校核人校核 (REVIEWER+) —— 两人不能是同一角色,
否则「设计人自己校核自己」等于没有校核。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.equipment import EquipmentList
from app.models.project import Workspace

pytestmark = pytest.mark.asyncio

DESIGN = {"扬程": {"value": 32.0, "unit": "m"}, "电机额定功率": {"value": 55.0, "unit": "kW"}}
ACTUAL_OK = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 56.0, "unit": "kW"}}
ACTUAL_BAD = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 48.0, "unit": "kW"}}


def _hdr(role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject='u', role=role)}"}


@pytest.fixture
def designer_headers() -> dict:
    return _hdr("DESIGNER")


@pytest.fixture
def reviewer_headers() -> dict:
    return _hdr("REVIEWER")


@pytest.fixture
def viewer_headers() -> dict:
    return _hdr("VIEWER")


@pytest.fixture
async def equipment(db_session: AsyncSession, project_id):
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


# ---------------------------------------------------------------------------
# confirm — 设计人
# ---------------------------------------------------------------------------


async def test_confirm_ok(client, equipment, designer_headers):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/confirm",
        json={"reason": "设计人确认满足工艺要求"}, headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actual_data_status"] == "PENDING_CONFIRM"


async def test_confirm_blocked_by_deviation(
    client, db_session, equipment, designer_headers
):
    eq = await db_session.get(EquipmentList, equipment.equipment_id)
    eq.actual_data_json = ACTUAL_BAD
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/confirm",
        json={"reason": "确认"}, headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "DEVIATION_BLOCKS_CONFIRMATION"
    assert "不合格" in body["message"]


async def test_confirm_rejects_viewer(client, equipment, viewer_headers):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/confirm",
        json={"reason": "x"}, headers=viewer_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_confirm_requires_auth(client, equipment):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/confirm", json={}
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# check — 校核人
# ---------------------------------------------------------------------------


async def test_check_pass_marks_confirmed(client, db_session, equipment, reviewer_headers):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "pass", "reason": "校核通过"},
        headers=reviewer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actual_data_status"] == "CONFIRMED"
    await db_session.refresh(equipment)
    assert equipment.actual_data_status == "CONFIRMED"


async def test_check_reject_reopens_entry(
    client, db_session, equipment, reviewer_headers
):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "reject", "reason": "数据存疑"},
        headers=reviewer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actual_data_status"] == "PENDING_CONFIRM"


async def test_check_rejects_designer(client, equipment, designer_headers):
    """设计人不能自己校核自己 —— 校核角色与设计角色必须分离."""
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "pass", "reason": "自批"}, headers=designer_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_check_rejects_unknown_decision(client, equipment, reviewer_headers):
    resp = await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "maybe"}, headers=reviewer_headers,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 已确认锁定（SPEC §3.2.4(5)）
# ---------------------------------------------------------------------------


async def test_put_blocked_after_confirm(client, db_session, equipment, designer_headers):
    await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "pass", "reason": "通过"}, headers=_hdr("REVIEWER"),
    )
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": [{"name": "扬程", "value": 34.0, "unit": "m"}]},
        headers=designer_headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "ACTUAL_DATA_LOCKED"


async def test_put_allowed_after_reject(client, equipment, designer_headers, reviewer_headers):
    await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "pass", "reason": "通过"}, headers=reviewer_headers,
    )
    await client.post(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
        json={"decision": "reject", "reason": "退回"}, headers=reviewer_headers,
    )
    resp = await client.put(
        f"/api/v1/equipment/{equipment.equipment_id}/actual-data",
        json={"entries": [{"name": "扬程", "value": 34.0, "unit": "m"}]},
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# D4 4A: 校核通过必经事件（API 层不绕过）
# ---------------------------------------------------------------------------


async def test_pass_check_goes_through_emit_event(
    client, db_session, equipment, reviewer_headers
):
    from app.services.events import (
        register_listener,
        restore_listeners,
        snapshot_listeners,
    )
    from app.services.supplier.confirmation_service import REPLACES_DESIGN

    snap = snapshot_listeners()
    try:
        seen: list[dict] = []

        async def _spy(event):  # listener 必须 async —— 派发器 await 它
            seen.append(event)

        register_listener(REPLACES_DESIGN, _spy)
        await client.post(
            f"/api/v1/equipment/{equipment.equipment_id}/actual-data/check",
            json={"decision": "pass", "reason": "通过"}, headers=reviewer_headers,
        )
    finally:
        restore_listeners(snap)

    assert len(seen) == 1
    # before 是 P8 反向恢复的唯一来源
    assert seen[0]["before"] == DESIGN


async def test_check_unknown_equipment_404(client, reviewer_headers):
    resp = await client.post(
        f"/api/v1/equipment/{uuid.uuid4()}/actual-data/check",
        json={"decision": "pass", "reason": "x"}, headers=reviewer_headers,
    )
    assert resp.status_code == 404, resp.text
