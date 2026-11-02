"""项目创建 API（`POST /projects`）+ 默认绑 RECORD 矩阵 —— P9B-2 · T-1。

## 为什么这个端点必须存在

PCS 长期**没有 Project create API**（`app/api/v1/projects.py` 只有
`GET /{project_id}` 与 `PATCH /{project_id}/product-category`）⇒ 项目**建不出来**
⇒ 而签署流程的对象（记录 / 交付物）全都挂在项目下 ⇒ P9B-2 交付后签署流程
在**真实 UI** 上走不通（只能靠 mock 验证）。

⚠️ **R-17 之后项目必须绑了 `module='RECORD'` 的矩阵**才能送审 ⇒
「项目创建」与「默认绑 RECORD 矩阵」必须**同批**，否则新项目建出来送不了审
⇒ 用户看到的是 422 而不是引导。

## 三条关键取舍（各有测试）

1. **创建项目是管理动作** ⇒ 限 SYSTEM_ADMIN（同文件既有的
   `PATCH /{id}/product-category` 同口径）。
2. **默认矩阵是全局内置模板**（固定名 + ACTIVE）⇒ 多个项目共用一份 ⇒
   「谁该签这一步」只有一个答案。
3. **默认绑**只在项目**还没绑** RECORD 矩阵时发生 ⇒ 人工改过的绑定**不被覆盖**
   （「谁该签」的决定权不在系统手里）。
"""

from __future__ import annotations

import contextlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.project import Project, Workspace
from app.services.signature_matrix_service import SignatureMatrixService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='admin-user', role='SYSTEM_ADMIN')}"
    }


@pytest.fixture
def designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='test-user', role='DESIGNER')}"
    }


@contextlib.asynccontextmanager
async def _guard_client(db_engine, raise_server_exceptions: bool = True):
    """独立 client —— **不**套 conftest 的 `check_user_project_access` bypass mock。

    默认 `client` fixture 把项目守卫 mock 成永远 True，在它上面测「越权被拒」
    是空断言：守卫根本没跑，测的只是一条不存在的路径。

    ⚠️ `raise_server_exceptions=False`：httpx ASGITransport 默认 **True**
    ⇒ 未捕获异常直接冒泡成测试失败，**看不到响应信封** ⇒ 断「全局兜底 500
    INTERNAL_ERROR」时必须显式关掉它。
    """
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
        transport=ASGITransport(app=app, raise_app_exceptions=raise_server_exceptions),
        base_url="http://test",
    ) as ac:
        yield ac


async def _make_workspace(db: AsyncSession, workspace_type: str = "FORMAL") -> uuid.UUID:
    workspace_id = uuid.uuid4()
    db.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type=workspace_type,
            name="WS",
            status="ACTIVE",
        )
    )
    await db.commit()
    return workspace_id


def _payload(workspace_id: uuid.UUID, **over: object) -> dict:
    payload = {
        "project_no": f"P-{uuid.uuid4().hex[:8]}",
        "project_name": "测试项目",
        "owner_company": "PCS",
        "location": "惠州",
        "project_type": "PETROLEUM",
        "design_phase": "EXECUTIVE_DESIGN",
        "unit_system": "SI",
        "workspace_id": str(workspace_id),
    }
    payload.update(over)
    return payload


async def _bound_matrix_id(db: AsyncSession, project_id: uuid.UUID) -> uuid.UUID:
    row = (
        await db.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id,
                ProjectSignatureMatrixBinding.module == "RECORD",
            )
        )
    ).scalar_one()
    return row.matrix_id


# ---------------------------------------------------------------------------
# POST /projects —— 必填字段 / 权限
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    [
        "project_no",
        "project_name",
        "owner_company",
        "location",
        "project_type",
        "design_phase",
        "unit_system",
        "workspace_id",
    ],
)
async def test_create_project_missing_required_field_is_422(
    client, db_session, admin_headers, missing
):
    """缺任一必填字段 ⇒ 422（不是 500）。"""
    workspace_id = await _make_workspace(db_session)
    payload = _payload(workspace_id)
    payload.pop(missing)
    resp = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert resp.status_code == 422, resp.text


async def test_create_project_requires_system_admin(client, db_session, designer_headers):
    """创建项目是管理动作 ⇒ 非 SYSTEM_ADMIN ⇒ 403。"""
    workspace_id = await _make_workspace(db_session)
    resp = await client.post(
        "/api/v1/projects", json=_payload(workspace_id), headers=designer_headers
    )
    assert resp.status_code == 403


async def test_create_project_unknown_workspace_is_404(client, db_session, admin_headers):
    """`workspace_id` 指向不存在的工作区 ⇒ 404（不建孤儿项目）。"""
    payload = _payload(uuid.uuid4())
    resp = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert resp.status_code == 404
    # ⚠️ 端点**不存在**时也是 404 ⇒ 光断言状态码是**空断言** ⇒ 断错误码，
    #    并且断「**没有**建出孤儿项目」。
    assert resp.json()["code"] == "WORKSPACE_NOT_FOUND"
    rows = await db_session.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.project_no == payload["project_no"])
    )
    assert rows == 0


# ---------------------------------------------------------------------------
# POST /projects —— 落库
# ---------------------------------------------------------------------------


async def test_create_project_persists_row(client, db_session, admin_headers):
    """创建成功 ⇒ 201 + project_id + project_no 落库；再查一次得到同一行。"""
    workspace_id = await _make_workspace(db_session)
    payload = _payload(workspace_id)
    resp = await client.post("/api/v1/projects", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    project_id = body["project_id"]
    assert body["project_no"] == payload["project_no"]

    row = (
        await db_session.execute(
            select(Project).where(Project.project_id == uuid.UUID(project_id))
        )
    ).scalar_one()
    assert row.project_no == payload["project_no"]
    assert row.project_name == payload["project_name"]
    assert row.workspace_id == workspace_id

    # 再查一次 ⇒ 同一行
    resp2 = await client.get(f"/api/v1/projects/{project_id}", headers=admin_headers)
    assert resp2.status_code == 200
    assert resp2.json()["project_no"] == payload["project_no"]


async def test_create_project_defaults_status_and_product_category(
    client, db_session, admin_headers
):
    """`status` / `product_category` 有模型默认 ⇒ 不必由客户端重复指定。"""
    workspace_id = await _make_workspace(db_session)
    resp = await client.post(
        "/api/v1/projects", json=_payload(workspace_id), headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    row = (
        await db_session.execute(
            select(Project).where(
                Project.project_id == uuid.UUID(resp.json()["project_id"])
            )
        )
    ).scalar_one()
    assert row.status == "ACTIVE"
    assert row.product_category == "OTHER"


# ---------------------------------------------------------------------------
# 默认绑 RECORD 矩阵
# ---------------------------------------------------------------------------


async def test_create_project_binds_default_record_matrix(client, db_session, admin_headers):
    """创建时自动绑一份 RECORD 矩阵 ⇒ 矩阵 ACTIVE + 3 步 CHECKER→REVIEWER→APPROVER。"""
    workspace_id = await _make_workspace(db_session)
    resp = await client.post(
        "/api/v1/projects", json=_payload(workspace_id), headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    project_id = uuid.UUID(resp.json()["project_id"])

    binding = (
        await db_session.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id,
                ProjectSignatureMatrixBinding.module == "RECORD",
            )
        )
    ).scalar_one()
    matrix = (
        await db_session.execute(
            select(SignatureMatrix).where(
                SignatureMatrix.matrix_id == binding.matrix_id
            )
        )
    ).scalar_one()
    assert matrix.status == "ACTIVE"
    assert matrix.module in ("RECORD", "*")
    steps = SignatureMatrixService.parse_steps(matrix)
    assert [s.sign_role for s in steps] == ["CHECKER", "REVIEWER", "APPROVER"]
    assert [s.step_order for s in steps] == [1, 2, 3]


async def test_ensure_default_record_matrix_is_idempotent(db_session):
    """再调一次「确保默认矩阵」⇒ 不产生第二行绑定、不产生第二份矩阵。"""
    workspace_id = await _make_workspace(db_session)
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
        )
    )
    await db_session.commit()

    await SignatureMatrixService.ensure_default_record_matrix(
        db_session, project_id=project_id
    )
    await db_session.commit()
    first_matrix_id = await _bound_matrix_id(db_session, project_id)

    await SignatureMatrixService.ensure_default_record_matrix(
        db_session, project_id=project_id
    )
    await db_session.commit()
    second_matrix_id = await _bound_matrix_id(db_session, project_id)

    assert first_matrix_id == second_matrix_id
    bindings = await db_session.scalar(
        select(func.count())
        .select_from(ProjectSignatureMatrixBinding)
        .where(
            ProjectSignatureMatrixBinding.project_id == project_id,
            ProjectSignatureMatrixBinding.module == "RECORD",
        )
    )
    assert bindings == 1
    matrices = await db_session.scalar(
        select(func.count())
        .select_from(SignatureMatrix)
        .where(SignatureMatrix.matrix_name == SignatureMatrixService.DEFAULT_RECORD_MATRIX_NAME)
    )
    assert matrices == 1


async def test_ensure_default_record_matrix_does_not_override_existing_binding(db_session):
    """默认矩阵已被人工改过（绑了别的矩阵）⇒ 不覆盖。"""
    workspace_id = await _make_workspace(db_session)
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
        )
    )
    await db_session.commit()

    # 人工建一份矩阵并绑上
    manual = await SignatureMatrixService.create_matrix(
        db_session,
        matrix_name="MANUAL-RECORD-MATRIX",
        module="RECORD",
        doc_type="RECORD",
        version_purpose="PUBLISHED",
        steps=[{"step_order": 1, "sign_role": "CHECKER"}],
        status="ACTIVE",
    )
    await SignatureMatrixService.bind_to_project(
        db_session, project_id=project_id, module="RECORD", matrix_id=manual.matrix_id
    )
    await db_session.commit()

    await SignatureMatrixService.ensure_default_record_matrix(
        db_session, project_id=project_id
    )
    await db_session.commit()

    assert await _bound_matrix_id(db_session, project_id) == manual.matrix_id


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/signature-matrices（读绑定）
# ---------------------------------------------------------------------------


async def test_list_project_bindings_returns_normalized_steps(
    client, db_session, admin_headers
):
    """读绑定 ⇒ 归一化的步骤（前端要的是「第 1 步该谁签」）。"""
    workspace_id = await _make_workspace(db_session)
    resp = await client.post(
        "/api/v1/projects", json=_payload(workspace_id), headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["project_id"]

    resp = await client.get(
        f"/api/v1/projects/{project_id}/signature-matrices", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["module"] == "RECORD"
    assert item["status"] == "ACTIVE"
    assert [s["sign_role"] for s in item["steps"]] == [
        "CHECKER",
        "REVIEWER",
        "APPROVER",
    ]
    # 归一化后的步骤字段（前端按这些字段读）
    assert set(item["steps"][0]) >= {
        "step_order",
        "sign_role",
        "required",
        "can_self_check",
        "can_skip",
    }


async def test_list_project_bindings_empty_when_no_binding(client, db_session, admin_headers):
    """项目没绑矩阵 ⇒ 空列表（前端**不禁用**，不猜 ⇒ 后端 422 兜底）。"""
    workspace_id = await _make_workspace(db_session)
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/projects/{project_id}/signature-matrices", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_list_project_bindings_404_for_other_project(
    db_engine, db_session, designer_headers
):
    """别人项目 ⇒ 404（不泄漏存在性）。"""
    workspace_id = await _make_workspace(db_session)
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
        )
    )
    await db_session.commit()

    async with _guard_client(db_engine) as ac:
        resp = await ac.get(
            f"/api/v1/projects/{project_id}/signature-matrices",
            headers=designer_headers,
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 评审 #4 / #5（P9B-2 整批评审 · 2026-10-29）
# ---------------------------------------------------------------------------


async def test_create_project_in_personal_workspace_is_rejected(
    client, admin_headers, db_session
):
    """PERSONAL 工作区里建项目 ⇒ 4xx（响亮），不是 201 + 「能送审」的假承诺。

    下游每个签署动作都过 `require_formal_project_workspace`（非 FORMAL ⇒ 403）
    ⇒ 收 201 的项目**永远送不了审** —— 正是端点 docstring 承诺不会出现的
    「项目建好了但送不了审」半成品。
    """
    ws_id = await _make_workspace(db_session, workspace_type="PERSONAL")

    resp = await client.post(
        "/api/v1/projects", headers=admin_headers, json=_payload(ws_id)
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "WORKSPACE_NOT_FORMAL"


async def test_create_project_duplicate_no_is_409_not_500(
    client, admin_headers, db_session, workspace
):
    """project_no 全局唯一 ⇒ 重复 POST ⇒ 409（可操作），不是裸 500。"""
    payload = _payload(workspace.workspace_id)

    r1 = await client.post("/api/v1/projects", headers=admin_headers, json=payload)
    assert r1.status_code == 201, r1.text
    r2 = await client.post("/api/v1/projects", headers=admin_headers, json=payload)

    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "PROJECT_NO_CONFLICT"


async def test_create_project_other_integrity_error_is_not_409(
    db_engine, db_session, admin_headers, workspace
):
    """⚠️ **别的**约束违约 ⇒ 不能说成「项目编号已存在」（TODO-102）。

    此前端点把**任何** `IntegrityError` 都报成 409「项目编号已存在」
    ⇒ 用户照提示去换编号，换了还是错（真相是另一个约束违约）。

    ## 为什么用 SQLite 触发器而不是「传个坏值」

    ⚠️ 计划建议的「`project_name=None` 触发 NOT NULL」**测不到这条** ——
    `project_name` 在 `ProjectCreate`（Pydantic）上就是必填 ⇒ 请求会先被
    **422** 拦掉（`min_length=1`），**根本走不到 DB** ⇒ 断言的是另一条路径。

    ⇒ 改用**真触发器**：在 `projects` 上挂一个 BEFORE INSERT 触发器，
    让**另一个**约束违约时抛 `IntegrityError`（SQLite 的 `RAISE(ABORT, …)`），
    消息里**不含** `project_no` ⇒ 端点必须**重新抛出**（⇒ 全局兜底 500），
    而不是映射成 409。

    ## 为什么用 `raise_server_exceptions=False` 的 client

    httpx ASGITransport 默认 `raise_server_exceptions=True` ⇒ 未捕获异常直接
    冒泡成测试失败，看不到**响应信封** ⇒ 这里用 False 断真实 500 信封。
    """
    from sqlalchemy import text

    await db_session.execute(
        text(
            "CREATE TRIGGER t_projects_other_violation BEFORE INSERT ON projects "
            "WHEN NEW.project_no = 'P-TRIGGER-FAIL' "
            "BEGIN SELECT RAISE(ABORT, 'CHECK constraint failed: some_other_rule'); END"
        )
    )
    await db_session.commit()

    async with _guard_client(db_engine, raise_server_exceptions=False) as ac:
        resp = await ac.post(
            "/api/v1/projects",
            headers=admin_headers,
            json=_payload(workspace.workspace_id, project_no="P-TRIGGER-FAIL"),
        )

    assert resp.status_code != 409, (
        f"别的约束违约被说成了「项目编号已存在」：{resp.text}"
    )
    assert resp.status_code == 500, resp.text
    body = resp.json()
    assert body["code"] == "INTERNAL_ERROR", body
    assert body["code"] != "PROJECT_NO_CONFLICT", body
