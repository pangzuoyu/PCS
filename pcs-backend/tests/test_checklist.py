"""Checklist API/服务测试（DICT-ALL-003 V3.1 表44 5态）。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_bulk_seed_returns_5_state_items(client, project_id, user_id):
    r = await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {
                    "item_key": "stream_flow",
                    "item_label": "物料流量",
                    "module": "stream",
                    "input_category": "REQUIRED",
                },
                {
                    "item_key": "fluid_props",
                    "item_label": "物性参数",
                    "module": "stream",
                    "input_category": "REQUIRED",
                },
            ]
        },
    )
    assert r.status_code == 201, r.text
    items = r.json()
    assert len(items) == 2
    for it in items:
        assert it["status"] == "NOT_STARTED"
        assert it["input_category"] in ("REQUIRED", "CONDITIONAL", "OPTIONAL")


async def test_invalid_status_rejected(client, project_id, user_id):
    seed = await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {
                    "item_key": "k",
                    "item_label": "l",
                    "input_category": "REQUIRED",
                }
            ]
        },
    )
    item_id = seed.json()[0]["checklist_id"]
    r = await client.put(
        f"/api/v1/checklist/items/{item_id}",
        params={"user_id": str(user_id)},
        json={"status": "WHATEVER"},
    )
    assert r.status_code == 422


async def test_update_to_verified_sets_verifier(client, project_id, user_id):
    seed = await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {
                    "item_key": "k",
                    "item_label": "l",
                    "input_category": "REQUIRED",
                }
            ]
        },
    )
    item_id = seed.json()[0]["checklist_id"]
    r = await client.put(
        f"/api/v1/checklist/items/{item_id}",
        params={"user_id": str(user_id)},
        json={"status": "VERIFIED", "source_type": "USER_INPUT"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "VERIFIED"
    assert body["verified_by"] == str(user_id)
    assert body["verified_at"] is not None


async def test_update_to_assumed_records_reason(client, project_id, user_id):
    seed = await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {
                    "item_key": "k",
                    "item_label": "l",
                    "input_category": "CONDITIONAL",
                }
            ]
        },
    )
    item_id = seed.json()[0]["checklist_id"]
    r = await client.put(
        f"/api/v1/checklist/items/{item_id}",
        params={"user_id": str(user_id)},
        json={
            "status": "ASSUMED",
            "assumption_reason": "default per SHELL-TEMA",
            "input_value_json": {"default": 1.0},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ASSUMED"
    assert body["assumption_reason"] == "default per SHELL-TEMA"
    assert body["input_value_json"] == {"default": 1.0}


async def test_completeness_pct_required_only(client, project_id, user_id):
    await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {"item_key": "r1", "item_label": "L", "input_category": "REQUIRED"},
                {"item_key": "r2", "item_label": "L", "input_category": "REQUIRED"},
                {"item_key": "o1", "item_label": "L", "input_category": "OPTIONAL"},
            ]
        },
    )
    r = await client.get(f"/api/v1/checklist/projects/{project_id}/completeness")
    assert r.status_code == 200
    body = r.json()
    assert body["required_total"] == 2
    assert body["required_verified"] == 0
    assert body["completeness_pct"] == 0.0


async def test_list_project_returns_all_items(client, project_id, user_id):
    await client.post(
        f"/api/v1/checklist/projects/{project_id}/seed",
        params={"user_id": str(user_id)},
        json={
            "items": [
                {"item_key": "a", "item_label": "A", "input_category": "REQUIRED"},
                {"item_key": "b", "item_label": "B", "input_category": "OPTIONAL"},
            ]
        },
    )
    r = await client.get(f"/api/v1/checklist/projects/{project_id}")
    assert r.status_code == 200
    assert len(r.json()) == 2