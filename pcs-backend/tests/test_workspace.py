"""Workspace API/服务测试。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_personal_workspace_default_retention(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={
            "workspace_type": "PERSONAL",
            "name": "alice-pipeline-poc",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["workspace_type"] == "PERSONAL"
    assert body["retention_days"] == 90
    assert body["name"] == "alice-pipeline-poc"


async def test_create_formal_workspace_null_retention(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "FORMAL", "name": "project-X"},
    )
    assert r.status_code == 201
    assert r.json()["retention_days"] is None


async def test_invalid_workspace_type_rejected(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "BOGUS", "name": "x"},
    )
    assert r.status_code == 422


async def test_get_workspace_touches_last_active(client, owner_id):
    create = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "PERSONAL", "name": "ws"},
    )
    ws_id = create.json()["workspace_id"]
    r = await client.get(f"/api/v1/workspaces/{ws_id}")
    assert r.status_code == 200
    assert r.json()["last_active_at"] is not None


async def test_get_nonexistent_returns_404(client):
    import uuid

    r = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}")
    assert r.status_code == 404