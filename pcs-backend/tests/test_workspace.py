"""Workspace API/服务测试。

⚠️ **P10-F · F3（TODO-186）**：本文件此前**全部不带 `Authorization` 头**
⇒ ⇒ 也就是说，它把「**匿名可读可建工作区**」**当成正常行为钉住了**
⇒ ⇒ ⇒ 那是 F3 审计查出的 critical ⇒ ⇒ ⇒ 现在这些用例**都带令牌**，
⇒ ⇒ ⇒ 且 `owner_id` 必须是**令牌里的那个人**。

⚠️ **「无权」与「不存在」必须同形**（`test_get_nonexistent_returns_404`
与 `tests/api/v1/test_workspace_access_guard.py` 各钉一半）。
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _auth(owner_id: uuid.UUID, role: str = "DESIGNER") -> dict[str, str]:
    token = create_access_token(
        subject=str(owner_id), role=role, extra={"user_id": str(owner_id)}
    )
    return {"Authorization": f"Bearer {token}"}


async def test_create_personal_workspace_default_retention(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={
            "workspace_type": "PERSONAL",
            "name": "alice-pipeline-poc",
        },
        headers=_auth(owner_id),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["workspace_type"] == "PERSONAL"
    assert body["retention_days"] == 90
    assert body["name"] == "alice-pipeline-poc"
    # ⚠️ **owner 必须是令牌里的那个人**（不是客户端填的那个）
    assert body["owner_id"] == str(owner_id)


async def test_create_formal_workspace_null_retention(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "FORMAL", "name": "project-X"},
        headers=_auth(owner_id),
    )
    assert r.status_code == 201
    assert r.json()["retention_days"] is None


async def test_invalid_workspace_type_rejected(client, owner_id):
    r = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "BOGUS", "name": "x"},
        headers=_auth(owner_id),
    )
    assert r.status_code == 422


async def test_get_workspace_touches_last_active(client, owner_id):
    create = await client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(owner_id)},
        json={"workspace_type": "PERSONAL", "name": "ws"},
        headers=_auth(owner_id),
    )
    ws_id = create.json()["workspace_id"]
    r = await client.get(
        f"/api/v1/workspaces/{ws_id}", headers=_auth(owner_id))
    assert r.status_code == 200
    assert r.json()["last_active_at"] is not None


async def test_get_nonexistent_returns_404(client, owner_id):
    r = await client.get(
        f"/api/v1/workspaces/{uuid.uuid4()}", headers=_auth(owner_id))
    assert r.status_code == 404


async def test_anonymous_cannot_list_workspaces(client):
    """⚠️ **匿名不得列工作区**（TODO-186）⇒ ⇒ 否则可枚举全部 `workspace_id`。"""
    r = await client.get("/api/v1/workspaces")
    assert r.status_code == 401, r.text
