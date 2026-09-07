"""StreamSymbol API 集成测试（SYM-3 / SUP-002 §8）。"""
import uuid

import pytest
import pytest_asyncio

from app.core.security import create_access_token
from app.models.project import Project, Workspace


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def pc_token() -> str:
    return create_access_token(subject="test-pc", role="PROCESS_CONTROLLER")


@pytest.fixture
def reviewer_token() -> str:
    return create_access_token(subject="test-r", role="REVIEWER")


@pytest.fixture
def approver_token() -> str:
    return create_access_token(subject="test-a", role="APPROVER")


@pytest.fixture
def designer_token() -> str:
    return create_access_token(subject="test-d", role="DESIGNER")


@pytest_asyncio.fixture
async def sample_project(db):
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="测试项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.commit()
    return proj


async def test_create_company_symbol_201(client, pc_token):
    r = await client.post(
        "/api/v1/stream-symbols",
        json={"symbol": "FOO", "name": "test", "category": "PROCESS"},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["symbol"] == "FOO" and body["status"] == "DRAFT"


async def test_create_company_symbol_403_for_designer(client, designer_token):
    r = await client.post(
        "/api/v1/stream-symbols",
        json={"symbol": "FOO", "name": "test"},
        headers=_auth(designer_token),
    )
    assert r.status_code == 403


async def test_list_company_symbols_designer_allowed(client, pc_token, designer_token):
    await client.post(
        "/api/v1/stream-symbols",
        json={"symbol": "FOO", "name": "test"},
        headers=_auth(pc_token),
    )
    r = await client.get("/api/v1/stream-symbols", headers=_auth(designer_token))
    assert r.status_code == 200
    assert any(x["symbol"] == "FOO" for x in r.json())


async def test_get_unknown_404(client, pc_token):
    r = await client.get(
        f"/api/v1/stream-symbols/{uuid.uuid4()}", headers=_auth(pc_token),
    )
    assert r.status_code == 404


async def test_fork_all_returns_list(
    client, pc_token, reviewer_token, approver_token, sample_project,
):
    # 先建公司级符号并发布
    r = await client.post(
        "/api/v1/stream-symbols",
        json={"symbol": "PUB", "name": "pub"},
        headers=_auth(pc_token),
    )
    sid = r.json()["symbol_id"]
    rr = await client.post(
        f"/api/v1/stream-symbols/{sid}/submit", headers=_auth(pc_token),
    )
    assert rr.status_code == 200, rr.text
    rr = await client.post(
        f"/api/v1/stream-symbols/{sid}/approve", headers=_auth(reviewer_token),
    )
    assert rr.status_code == 200, rr.text
    rr = await client.post(
        f"/api/v1/stream-symbols/{sid}/publish", headers=_auth(approver_token),
    )
    assert rr.status_code == 200, rr.text

    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols/fork",
        json={}, headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    assert any(x["symbol"] == "PUB" for x in r.json())


async def test_add_project_symbol_201(client, pc_token, sample_project):
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols",
        json={"symbol": "LOC", "name": "local"},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["symbol"] == "LOC"


async def test_list_project_symbols(client, pc_token, sample_project):
    await client.post(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols",
        json={"symbol": "LOC", "name": "x"},
        headers=_auth(pc_token),
    )
    r = await client.get(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols",
        headers=_auth(pc_token),
    )
    assert r.status_code == 200
    assert any(x["symbol"] == "LOC" for x in r.json())


async def test_update_project_symbol(client, pc_token, sample_project):
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols",
        json={"symbol": "UP", "name": "x"},
        headers=_auth(pc_token),
    )
    pid = r.json()["project_symbol_id"]
    r = await client.put(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols/{pid}",
        json={"override": {"k": "v"}, "name": "新名"},
        headers=_auth(pc_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "新名"
    assert r.json()["override_json"]["k"] == "v"


async def test_delete_project_symbol_204(client, pc_token, sample_project):
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols",
        json={"symbol": "DEL", "name": "x"},
        headers=_auth(pc_token),
    )
    pid = r.json()["project_symbol_id"]
    r = await client.delete(
        f"/api/v1/projects/{sample_project.project_id}/stream-symbols/{pid}",
        headers=_auth(pc_token),
    )
    assert r.status_code == 204