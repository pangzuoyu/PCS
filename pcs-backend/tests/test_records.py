"""Records API 端到端（Sprint 2）。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _make_formal_ws(client, owner_id: str) -> str:
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": owner_id},
        json={"workspace_type": "FORMAL", "name": "formal"},
    )
    assert r.status_code == 201, r.text
    return r.json()["workspace_id"]


async def _create_piping(client, ws_id: str, user_id: str, line_no: str = "P-100"):
    r = await client.post(
        f"/api/v1/records/piping?workspace_id={ws_id}&user_id={user_id}",
        json={
            "project_id": "00000000-0000-0000-0000-000000000001",
            "line_no": line_no,
            "norm_oper_press": 1.0,
            "max_oper_press": 1.5,
            "norm_oper_temp": 40.0,
            "max_oper_temp": 80.0,
            "design_press": 2.0,
            "design_temp": 100.0,
            "piping_category": "GC2",
            "pressure_test_medium": "WATER",
            "pressure_test_press": 3.0,
            "check_class": "II",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["pipe_id"]


async def test_create_piping_in_formal(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    assert pipe_id


async def test_create_piping_in_personal_403(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": owner_id},
        json={"workspace_type": "PERSONAL", "name": "personal"},
    )
    ws_id = r.json()["workspace_id"]
    r = await client.post(
        f"/api/v1/records/piping?workspace_id={ws_id}&user_id={owner_id}",
        json={
            "project_id": "00000000-0000-0000-0000-000000000001",
            "line_no": "P-100",
        },
    )
    assert r.status_code == 403


async def test_transition_draft_to_in_approval(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    r = await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "SUBMIT_FOR_CHECK"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sign_status"] == "IN_APPROVAL"


async def test_transition_in_approval_to_checked(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "SUBMIT_FOR_CHECK"},
    )
    r = await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=CHECKER",
        json={"transition": "PASS_CHECK"},
    )
    assert r.status_code == 200
    assert r.json()["sign_status"] == "CHECKED"


async def test_transition_role_forbidden(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "SUBMIT_FOR_CHECK"},
    )
    r = await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "PASS_CHECK"},
    )
    assert r.status_code == 409


async def test_invalid_transition_409(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    r = await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "APPLY_CHANGE"},
    )
    assert r.status_code == 409


async def test_obsolete_piping(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    r = await client.request(
        "DELETE",
        f"/api/v1/records/piping/{pipe_id}"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER&reason=test",
    )
    assert r.status_code == 200, r.text
    assert r.json()["sign_status"] == "OBSOLETE"


async def test_list_piping(client, owner_id):
    ws_id = await _make_formal_ws(client, owner_id)
    await _create_piping(client, ws_id, owner_id, "P-100")
    await _create_piping(client, ws_id, owner_id, "P-101")
    r = await client.get(f"/api/v1/records/piping?workspace_id={ws_id}")
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_snapshot_created_for_apply_change(client, owner_id):
    """apply_change 触发快照创建。"""

    ws_id = await _make_formal_ws(client, owner_id)
    pipe_id = await _create_piping(client, ws_id, owner_id)
    # 推进到 CHECKED
    await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "SUBMIT_FOR_CHECK"},
    )
    await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=CHECKER",
        json={"transition": "PASS_CHECK"},
    )
    # CHECKED → CHANGE_PENDING（主动变更路径，触发快照）
    await client.post(
        f"/api/v1/records/piping/{pipe_id}/transition"
        f"?workspace_id={ws_id}&user_id={owner_id}&actor_role=DESIGNER",
        json={"transition": "INITIATE_CHANGE"},
    )
    r = await client.get(f"/api/v1/records/piping/{pipe_id}/snapshots?workspace_id={ws_id}")
    assert r.status_code == 200
    snaps = r.json()
    assert len(snaps) >= 1
    statuses = {s["snapshot_status"] for s in snaps}
    assert "ACTIVE" in statuses