"""P9A-DLV-011 新端点的**项目授权**测试（评审 I-6）。

## 为什么这组测试必须用**独立 client**

默认 `client` fixture 把 `UserProjectService.check_user_project_access`
mock 成**恒 True**（见 `tests/conftest.py`）⇒ 在它上面测「越权被拒」是
**空断言**：守卫根本没跑，测的只是一条不存在的路径。

⇒ 这里照 `tests/api/v1/test_workflow_progress_api.py` 的 `_guard_client`
模式另起一个 client，**不**套那个 mock ⇒ 守卫真的跑。

## 钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | 新端点**不查项目授权**（或查了但写在写之后） | 越权 ⇒ 404，**且什么都没改** |
| RF-2 | 守卫顺序错（先写后鉴权）⇒ 越权请求把行改了才 404 | 越权 ⇒ 数据未变 |
"""
from __future__ import annotations

import contextlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc import ReliefResult
from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import RecordSignStatus9, ReliefScenario
from app.models.project import Project, UserProject, Workspace

pytestmark = pytest.mark.asyncio

MODULE = "ReliefResult"


def _token(*, role: str, subject: str = "dlv011-outsider"):
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token(subject=subject, role=role)}"
    }


@contextlib.asynccontextmanager
async def _guard_client(db_engine):
    """独立 client —— **不**套 conftest 的 `check_user_project_access` bypass mock。"""
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.api.v1 import api_router
    from app.core.errors import install_exception_handlers
    from app.db.session import get_db

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI(title="PCS Test Guard")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def _make_project(db: AsyncSession) -> Project:
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="越权测试项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    return proj


async def _make_record(db: AsyncSession, *, project: Project) -> ReliefResult:
    rec = ReliefResult(
        project_id=project.project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9.CHECKED,
        record_hash="h1",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _make_matrix(db: AsyncSession) -> SignatureMatrix:
    matrix = SignatureMatrix(
        matrix_name="越权测试矩阵",
        module="RECORD",
        doc_type="CALCULATION_BOOK",
        version_purpose="ISSUED_FOR_CONSTRUCTION",
        steps_json=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    return matrix


# ---------------------------------------------------------------------------
# 记录侧三个端点
# ---------------------------------------------------------------------------


async def test_initiate_change_requires_project_access(db, db_engine):
    """越权发起变更 ⇒ 404，**且记录状态没变**。"""
    project = await _make_project(db)
    rec = await _make_record(db, project=project)
    # ⚠️ **必须先提交**：in-memory SQLite 的 StaticPool 让 `db` 与 guard client
    # **共用同一条连接** ⇒ guard client 退出时的 rollback 会把 `db` 这边
    # 未提交的 INSERT 一起回滚掉（2026-10-26 实测：refresh 报
    # "Could not refresh instance"）。
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.post(
            f"/api/v1/records/{MODULE}/{rec.relief_id}/initiate-change",
            json={"reason": "越权发起"},
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 404, resp.text
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED, "越权请求不该改状态"


async def test_apply_change_requires_project_access(db, db_engine):
    """越权提交变更完成 ⇒ 404。"""
    project = await _make_project(db)
    rec = await _make_record(db, project=project)
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.post(
            f"/api/v1/records/{MODULE}/{rec.relief_id}/apply-change",
            json={"reason": "越权提交"},
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 404, resp.text
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED, "越权请求不该改状态"


async def test_change_notice_requires_project_access(db, db_engine):
    """越权建变更单 ⇒ 404，**且没建出交付物**。"""
    from app.models.deliverable import Deliverable

    project = await _make_project(db)
    rec = await _make_record(db, project=project)
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.post(
            f"/api/v1/records/{MODULE}/{rec.relief_id}/change-notice",
            json={
                "change_type": "DATA_CORRECTION",
                "reason": "越权建单",
                "triggered_by": "MANUAL",
            },
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 404, resp.text
    rows = (
        await db.execute(
            select(Deliverable).where(Deliverable.project_id == project.project_id)
        )
    ).scalars().all()
    assert rows == [], "越权请求不该建出交付物"


# ---------------------------------------------------------------------------
# 矩阵绑定两个端点
# ---------------------------------------------------------------------------


async def test_bind_matrix_requires_project_access(db, db_engine):
    """越权给项目绑矩阵 ⇒ 404，**且没建出绑定行**。"""
    project = await _make_project(db)
    matrix = await _make_matrix(db)
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.post(
            f"/api/v1/projects/{project.project_id}/signature-matrices",
            json={"module": "RECORD", "matrix_id": str(matrix.matrix_id)},
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 404, resp.text
    rows = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project.project_id
            )
        )
    ).scalars().all()
    assert rows == [], "越权请求不该建出绑定行"


async def test_unbind_matrix_requires_project_access(db, db_engine):
    """越权解绑项目矩阵 ⇒ 404，**且绑定还在**。"""
    project = await _make_project(db)
    matrix = await _make_matrix(db)
    db.add(
        ProjectSignatureMatrixBinding(
            project_id=project.project_id, module="RECORD", matrix_id=matrix.matrix_id
        )
    )
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.delete(
            f"/api/v1/projects/{project.project_id}/signature-matrices/RECORD",
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 404, resp.text
    rows = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project.project_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1, "越权请求不该解绑"


async def test_project_member_is_allowed(db, db_engine):
    """反向对照：**有**项目授权的人不被这条门挡住（别把门修成永远 404）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project=project)
    db.add(
        UserProject(
            user_id=uuid.uuid5(uuid.NAMESPACE_DNS, "dlv011-outsider"),
            project_id=project.project_id,
            role_in_project="DESIGNER",
        )
    )
    await db.commit()
    async with _guard_client(db_engine) as ac:
        resp = await ac.post(
            f"/api/v1/records/{MODULE}/{rec.relief_id}/initiate-change",
            json={"reason": "有授权"},
            headers=_token(role="DESIGNER"),
        )
    assert resp.status_code == 200, resp.text
