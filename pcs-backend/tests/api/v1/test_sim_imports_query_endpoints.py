"""P3.x SIM-27: 9 类 sim imports 查询端点 测试。

spec §5.5：sim_imports 9 维度查询覆盖（通过 query params + 5 GET 端点）。
9 维度：project_id / status / import_type / source_file_name / banner_version /
       created_by / date_from+date_to / has_warnings / convergence_status

5 GET 端点：
- GET /projects/{project_id}/imports（paginated list + 8 query param 过滤）
- GET /imports/{import_id}（单条 fetch）
- GET /imports/{import_id}/warnings（关联 warnings）
- GET /imports/{import_id}/preview-streams（status==PREVIEW 才可读）
- GET /imports/expired（批量列已过期）
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.sim_import import (
    SimImport,
    SimImportStatus,
    SimImportType,
    SimImportWarning,
    SimImportWarningSeverity,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="sim27-test", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    from app.models.project import Project, Workspace

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="SIM27 测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj

    return _make


def _mk(
    db,
    project_id,
    workspace_id,
    *,
    status=SimImportStatus.PREVIEW,
    type_=SimImportType.PROII,
    source="sample.inp",
    convergence=None,
    preview_streams=None,
    expires_at=None,
    warnings=None,
):
    return SimImport(
        project_id=project_id,
        workspace_id=workspace_id,
        import_type=type_,
        status=status,
        source_file_name=source,
        convergence_status=convergence,
        banner_version="8.5",
        preview_streams_json=preview_streams or {},
        warnings_json=warnings or [],
        created_by=uuid.uuid4(),
        expires_at=expires_at or (datetime.now(UTC) + timedelta(hours=24)),
    )


# ---------------------------------------------------------------------------
# 1) GET /projects/{project_id}/imports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_imports_paginated(
    client, designer_headers, db, make_project
):
    """默认 list：返回当前 project 全部 imports。"""
    proj = await make_project()
    for _ in range(3):
        db.add(_mk(db, proj.project_id, proj.workspace_id))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_list_imports_filter_by_status(
    client, designer_headers, db, make_project
):
    """status=COMMITTED 仅返回已提交的。"""
    proj = await make_project()
    db.add(_mk(db, proj.project_id, proj.workspace_id, status=SimImportStatus.PREVIEW))
    db.add(_mk(db, proj.project_id, proj.workspace_id, status=SimImportStatus.COMMITTED))
    db.add(_mk(db, proj.project_id, proj.workspace_id, status=SimImportStatus.EXPIRED))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        params={"status": "COMMITTED"},
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "COMMITTED"


@pytest.mark.asyncio
async def test_list_imports_filter_by_import_type(
    client, designer_headers, db, make_project
):
    """import_type=EXCEL 仅返回 Excel 来源。"""
    proj = await make_project()
    db.add(_mk(db, proj.project_id, proj.workspace_id, type_=SimImportType.PROII))
    db.add(_mk(db, proj.project_id, proj.workspace_id, type_=SimImportType.EXCEL))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        params={"import_type": "EXCEL"},
        headers=designer_headers,
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["import_type"] == "EXCEL"


@pytest.mark.asyncio
async def test_list_imports_filter_by_convergence(
    client, designer_headers, db, make_project
):
    """convergence_status 精确匹配。"""
    proj = await make_project()
    db.add(_mk(db, proj.project_id, proj.workspace_id, convergence="CONVERGED"))
    db.add(_mk(db, proj.project_id, proj.workspace_id, convergence="NOT_CONVERGED"))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        params={"convergence_status": "CONVERGED"},
        headers=designer_headers,
    )
    body = resp.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_list_imports_filter_combined(
    client, designer_headers, db, make_project
):
    """多条件组合：status + import_type + convergence。"""
    proj = await make_project()
    # 匹配：PROII + COMMITTED + CONVERGED
    db.add(
        _mk(
            db,
            proj.project_id,
            proj.workspace_id,
            type_=SimImportType.PROII,
            status=SimImportStatus.COMMITTED,
            convergence="CONVERGED",
        )
    )
    # 不匹配
    db.add(
        _mk(
            db,
            proj.project_id,
            proj.workspace_id,
            type_=SimImportType.EXCEL,
            status=SimImportStatus.COMMITTED,
            convergence="CONVERGED",
        )
    )
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        params={
            "status": "COMMITTED",
            "import_type": "PROII",
            "convergence_status": "CONVERGED",
        },
        headers=designer_headers,
    )
    body = resp.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_list_imports_pagination(
    client, designer_headers, db, make_project
):
    """分页：limit + offset。"""
    proj = await make_project()
    for _ in range(5):
        db.add(_mk(db, proj.project_id, proj.workspace_id))
    await db.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/imports",
        params={"limit": 2, "offset": 0},
        headers=designer_headers,
    )
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# 2) GET /imports/{import_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_import_by_id(
    client, designer_headers, db, make_project
):
    """单条 fetch。"""
    proj = await make_project()
    imp = _mk(db, proj.project_id, proj.workspace_id, source="test.inp")
    db.add(imp)
    await db.commit()
    await db.refresh(imp)

    resp = await client.get(
        f"/api/v1/imports/{imp.import_id}",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["import_id"] == str(imp.import_id)
    assert body["source_file_name"] == "test.inp"


@pytest.mark.asyncio
async def test_get_import_by_id_not_found(client, designer_headers):
    """不存在 → 404。"""
    resp = await client.get(
        f"/api/v1/imports/{uuid.uuid4()}",
        headers=designer_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3) GET /imports/{import_id}/preview-streams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_preview_streams_blocked_when_committed(
    client, designer_headers, db, make_project
):
    """preview-streams 仅 PREVIEW 状态可读；COMMITTED → 410。"""
    proj = await make_project()
    imp = _mk(
        db,
        proj.project_id,
        proj.workspace_id,
        status=SimImportStatus.COMMITTED,
        preview_streams={"streams": [{"id": "S1"}]},
    )
    db.add(imp)
    await db.commit()
    await db.refresh(imp)

    resp = await client.get(
        f"/api/v1/imports/{imp.import_id}/preview-streams",
        headers=designer_headers,
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_get_preview_streams_ok_when_preview(
    client, designer_headers, db, make_project
):
    """PREVIEW 状态可读。"""
    proj = await make_project()
    imp = _mk(
        db,
        proj.project_id,
        proj.workspace_id,
        status=SimImportStatus.PREVIEW,
        preview_streams={"streams": [{"id": "S1"}]},
    )
    db.add(imp)
    await db.commit()
    await db.refresh(imp)

    resp = await client.get(
        f"/api/v1/imports/{imp.import_id}/preview-streams",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["streams"][0]["id"] == "S1"


# ---------------------------------------------------------------------------
# 4) GET /imports/{import_id}/warnings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_warnings_for_import(
    client, designer_headers, db, make_project
):
    """列出指定 import 的所有 warnings（按 severity 排序）。"""
    proj = await make_project()
    imp = _mk(db, proj.project_id, proj.workspace_id)
    db.add(imp)
    await db.flush()
    db.add(
        SimImportWarning(
            import_id=imp.import_id,
            severity=SimImportWarningSeverity.WARN,
            message="WARN msg",
        )
    )
    db.add(
        SimImportWarning(
            import_id=imp.import_id,
            severity=SimImportWarningSeverity.INFO,
            message="INFO msg",
        )
    )
    await db.commit()

    resp = await client.get(
        f"/api/v1/imports/{imp.import_id}/warnings",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


# ---------------------------------------------------------------------------
# 5) GET /imports/expired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_expired(client, designer_headers, db, make_project):
    """列 expires_at < now 的 imports。"""
    proj = await make_project()
    db.add(
        _mk(
            db,
            proj.project_id,
            proj.workspace_id,
            expires_at=datetime.now(UTC) - timedelta(hours=24),
        )
    )
    db.add(
        _mk(
            db,
            proj.project_id,
            proj.workspace_id,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/imports/expired",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1