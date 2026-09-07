"""管道代码 API 集成测试（FMT-4）。

覆盖：template CRUD + project fork + generate endpoint + validate endpoint +
5 态流。
"""
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


_VALID_FMT = {
    "separator": "-",
    "segments": [
        {"key": "sym", "type": "stream_symbol", "length": 10, "position": 1},
        {"key": "seq", "type": "auto_increment", "length": 3, "position": 2},
    ],
}


async def _publish_template_via_api(client, pc_token, reviewer_token, approver_token, name="T-1"):
    r = await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": name, "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    tid = r.json()["template_id"]
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/submit", headers=_auth(pc_token),
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/approve", headers=_auth(reviewer_token),
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/publish", headers=_auth(approver_token),
    )
    assert r.status_code == 200, r.text
    return tid


# ---------- 公司级模板 ----------


async def test_create_template_201(client, pc_token):
    r = await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": "T-1", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["template_name"] == "T-1"
    assert body["status"] == "DRAFT"


async def test_create_template_403_for_designer(client, designer_token):
    r = await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": "T-2", "format_definition_json": _VALID_FMT},
        headers=_auth(designer_token),
    )
    assert r.status_code == 403


async def test_list_templates_designer_allowed(client, pc_token, designer_token):
    await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": "T-3", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    r = await client.get("/api/v1/pipe-code-templates", headers=_auth(designer_token))
    assert r.status_code == 200
    assert any(x["template_name"] == "T-3" for x in r.json())


async def test_template_5_state_flow(
    client, pc_token, reviewer_token, approver_token,
):
    r = await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": "T-FLOW", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    tid = r.json()["template_id"]
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/submit", headers=_auth(pc_token),
    )
    assert r.status_code == 200 and r.json()["status"] == "PENDING"
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/approve", headers=_auth(reviewer_token),
    )
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    r = await client.post(
        f"/api/v1/pipe-code-templates/{tid}/publish", headers=_auth(approver_token),
    )
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"


# ---------- 项目级 ----------


async def test_fork_to_project_201(
    client, pc_token, reviewer_token, approver_token, sample_project,
):
    tid = await _publish_template_via_api(
        client, pc_token, reviewer_token, approver_token, name="T-FORK",
    )
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs/fork",
        json={"template_id": tid, "config_name": "CFG-FORK"},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["config_name"] == "CFG-FORK"
    assert body["status"] == "DRAFT"
    assert body["source_template_id"] == tid


async def test_create_project_config_201(client, pc_token, sample_project):
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs",
        json={"config_name": "CFG-NEW", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["config_name"] == "CFG-NEW"


async def test_list_project_configs(client, pc_token, sample_project):
    await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs",
        json={"config_name": "CFG-L", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    r = await client.get(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs",
        headers=_auth(pc_token),
    )
    assert r.status_code == 200
    assert any(x["config_name"] == "CFG-L" for x in r.json())


# ---------- 生成/验证 ----------


async def test_generate_pipe_code_200(
    client, pc_token, reviewer_token, approver_token, db, sample_project,
):
    """完整端到端：建模板 → 发布 → fork → 提交/审批/发布 → 生成代码。

    生成需要已发布的项目级配置 + 项目内有效 stream_symbol。
    """
    from app.services.stream_symbol_service import StreamSymbolService

    # 加项目符号 FOO（active）
    await StreamSymbolService.add_project_symbol(
        db, project_id=sample_project.project_id,
        symbol="FOO", name="符号 FOO", category="PROCESS",
        actor=type("A", (), {"user_id": uuid.uuid4()})(),
    )
    tid = await _publish_template_via_api(
        client, pc_token, reviewer_token, approver_token, name="T-GEN",
    )
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs/fork",
        json={"template_id": tid, "config_name": "CFG-GEN"},
        headers=_auth(pc_token),
    )
    cid = r.json()["config_id"]
    # 走完项目 5 态到 PUBLISHED
    for action in ["submit", "approve", "publish"]:
        role = pc_token if action in ("submit",) else (
            reviewer_token if action == "approve" else pc_token
        )
        rr = await client.post(
            f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs/{cid}/{action}",
            headers=_auth(role),
        )
        assert rr.status_code == 200, (action, rr.text)

    r = await client.post(
        "/api/v1/pipe-codes/generate",
        json={"project_id": str(sample_project.project_id),
              "input_segments": {"stream_symbol": "FOO"}},
        headers=_auth(pc_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "FOO-001"


async def test_validate_pipe_code_200(
    client, pc_token, reviewer_token, approver_token, db, sample_project,
):
    from app.services.stream_symbol_service import StreamSymbolService
    await StreamSymbolService.add_project_symbol(
        db, project_id=sample_project.project_id,
        symbol="FOO", name="符号 FOO", category="PROCESS",
        actor=type("A", (), {"user_id": uuid.uuid4()})(),
    )
    tid = await _publish_template_via_api(
        client, pc_token, reviewer_token, approver_token, name="T-VAL",
    )
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs/fork",
        json={"template_id": tid, "config_name": "CFG-VAL"},
        headers=_auth(pc_token),
    )
    cid = r.json()["config_id"]
    for action in ["submit", "approve", "publish"]:
        role = pc_token if action in ("submit",) else (
            reviewer_token if action == "approve" else pc_token
        )
        rr = await client.post(
            f"/api/v1/projects/{sample_project.project_id}/pipe-code-configs/{cid}/{action}",
            headers=_auth(role),
        )
        assert rr.status_code == 200

    r = await client.post(
        "/api/v1/pipe-codes/validate",
        json={"project_id": str(sample_project.project_id), "code": "FOO-002"},
        headers=_auth(pc_token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert body["segments"]["sym"] == "FOO"
    assert body["segments"]["seq"] == "002"


async def test_delete_template_204(client, pc_token):
    r = await client.post(
        "/api/v1/pipe-code-templates",
        json={"template_name": "T-DEL", "format_definition_json": _VALID_FMT},
        headers=_auth(pc_token),
    )
    tid = r.json()["template_id"]
    r = await client.delete(
        f"/api/v1/pipe-code-templates/{tid}", headers=_auth(pc_token),
    )
    assert r.status_code == 204
