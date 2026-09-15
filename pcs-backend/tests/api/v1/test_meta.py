"""Meta API 测试（P4.5 P45-0-4）。

4 端点 × 1 happy + 1 anonymous denied = 8 例。
"""
from __future__ import annotations


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ---------- happy path ----------


async def test_get_enums_returns_seven_groups(client, sample_user_token):
    r = await client.get("/api/v1/meta/enums", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    # 7 enum 组
    for key in (
        "RecordSignStatus",
        "StreamSignStatus",
        "DeliverableStatus",
        "WorkspaceType",
        "EquipmentStatus",
        "CalcStatus",
        "SnapshotStatus",
    ):
        assert key in data, f"missing enum group {key}"
        assert isinstance(data[key], list)
        assert data[key], f"{key} is empty"
    # RecordSignStatus 9 态全集（UI Spec §6.1）
    values = [item["value"] for item in data["RecordSignStatus"]]
    assert values == [
        "DRAFT",
        "IN_APPROVAL",
        "CHECKED",
        "CHECK_REJECTED",
        "STALE",
        "CHANGE_PENDING",
        "CHANGED",
        "REVERSAL_PENDING",
        "OBSOLETE",
    ]
    # 颜色 + icon 与 tokens.css 对齐
    draft = data["RecordSignStatus"][0]
    assert draft["color"] == "state-draft"
    assert draft["icon"] == "EditOutlined"


async def test_get_permissions_skeleton(client, sample_user_token):
    r = await client.get("/api/v1/meta/permissions", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert data, "permissions 骨架不应为空"
    for p in data:
        assert {"role", "resource", "action", "permission_code", "frontend_behavior"} <= p.keys()


async def test_get_error_codes_skeleton(client, sample_user_token):
    r = await client.get("/api/v1/meta/error-codes", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert data, "error codes 骨架不应为空"
    codes = {e["code"] for e in data}
    assert "PCS-4031" in codes
    for e in data:
        assert {"code", "http", "message", "ui_behavior"} <= e.keys()


async def test_get_state_machine(client, sample_user_token):
    r = await client.get("/api/v1/meta/state-machine", headers=_auth(sample_user_token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transitions" in data and "allowed" in data
    # DRAFT 可 SUBMIT / OBSOLETE
    assert sorted(data["allowed"]["DRAFT"]) == ["OBSOLETE", "SUBMIT"]
    # OBSOLETE 无后续动作
    assert data["allowed"]["OBSOLETE"] == []
    # transitions 列表非空
    assert data["transitions"]
    for t in data["transitions"]:
        assert "from" in t and "action" in t


# ---------- anonymous denied ----------


async def test_enums_anonymous_denied(client):
    r = await client.get("/api/v1/meta/enums")
    assert r.status_code == 401


async def test_permissions_anonymous_denied(client):
    r = await client.get("/api/v1/meta/permissions")
    assert r.status_code == 401


async def test_error_codes_anonymous_denied(client):
    r = await client.get("/api/v1/meta/error-codes")
    assert r.status_code == 401


async def test_state_machine_anonymous_denied(client):
    r = await client.get("/api/v1/meta/state-machine")
    assert r.status_code == 401