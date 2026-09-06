"""管道等级 API 测试（Task 1.9.2 / spec §3.2.5 5 端点 + 删除/分配）。

PC-1 SUP-002 schema 重构后，1.9 薄层契约（3 态 + 复合 PK + class_id assign）已废止。
以下 3 个用例标 xfail(strict=False)，由 PC-3 service 层 + PC-6 API 替换：
- test_crud_roundtrip（status='ACTIVE'）
- test_delete_in_use_409（ProjectPipeClass 复合 PK 取参）
- test_project_list（同上）
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.models.project import Project, Workspace

_BODY = {
    "class_id": "A1", "class_name": "管道等级 A1", "material_standard": "GB/T 8163",
    "corrosion_allowance": 1.5, "design_pressure": 2.5, "design_temperature": 200.0,
    "dn_series_json": {"min": 15, "max": 350},
    "sch_series_json": {"15": "40", "350": "STD"},
    "flange_class": "PN25", "source": "COMPANY_STD", "version": "PC-V1.0",
}


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest_asyncio.fixture
async def sample_project(db):
    """conftest 无 sample_project → 本文件内定义（Workspace→Project 链，
    同 tests/services/test_pipe_class_service.py 的 make_project）。"""
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


@pytest.mark.xfail(reason="PC-1 schema 重构废止 1.9 薄层 3 态契约，PC-3 service 层替换", strict=False)
async def test_crud_roundtrip(client, sample_pc_token):
    r = await client.post("/api/v1/pipe-classes", json=_BODY, headers=_auth(sample_pc_token))
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"

    r = await client.get("/api/v1/pipe-classes", headers=_auth(sample_pc_token))
    assert r.status_code == 200 and [c["class_id"] for c in r.json()] == ["A1"]

    r = await client.get("/api/v1/pipe-classes/A1", headers=_auth(sample_pc_token))
    assert r.status_code == 200

    r = await client.put("/api/v1/pipe-classes/A1", json={**_BODY, "status": "ACTIVE"},
                         headers=_auth(sample_pc_token))
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"

    r = await client.delete("/api/v1/pipe-classes/A1", headers=_auth(sample_pc_token))
    assert r.status_code == 204  # 未被引用 → 可删

    r = await client.get("/api/v1/pipe-classes/A1", headers=_auth(sample_pc_token))
    assert r.status_code == 404


async def test_update_class_id_mismatch_422(client, sample_pc_token):
    """评审 Important：PUT body.class_id 与路径不一致 → 422（防 model_dump 覆写主键）。"""
    await client.post("/api/v1/pipe-classes", json=_BODY, headers=_auth(sample_pc_token))
    r = await client.put(
        "/api/v1/pipe-classes/A1",
        json={**_BODY, "class_id": "B2", "status": "ACTIVE"},
        headers=_auth(sample_pc_token),
    )
    assert r.status_code == 422


@pytest.mark.xfail(reason="PC-1 schema 重构废止 ProjectPipeClass 复合 PK，PC-3 service 层替换", strict=False)
async def test_delete_in_use_409(client, sample_pc_token, sample_project):
    await client.post("/api/v1/pipe-classes", json=_BODY, headers=_auth(sample_pc_token))
    r = await client.post(
        f"/api/v1/projects/{sample_project.project_id}/pipe-classes",
        json={"class_id": "A1"}, headers=_auth(sample_pc_token))
    assert r.status_code == 201
    r = await client.delete("/api/v1/pipe-classes/A1", headers=_auth(sample_pc_token))
    assert r.status_code == 409  # 已用等级不可删除


@pytest.mark.xfail(reason="PC-1 schema 重构废止 ProjectPipeClass 复合 PK，PC-3 service 层替换", strict=False)
async def test_project_list(client, sample_pc_token, sample_project):
    r = await client.get(f"/api/v1/projects/{sample_project.project_id}/pipe-classes",
                         headers=_auth(sample_pc_token))
    assert r.status_code == 200 and r.json() == []


async def test_create_requires_pc_role(client, sample_user_token):
    r = await client.post("/api/v1/pipe-classes", json=_BODY, headers=_auth(sample_user_token))
    assert r.status_code == 403


async def test_list_denied_anonymous(client):
    r = await client.get("/api/v1/pipe-classes")
    assert r.status_code in (401, 403)
