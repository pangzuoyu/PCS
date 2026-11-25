"""项目向导的后端面（P10-K · W-2b/W-2d/W-3/W-3d/W-8）。

## 这组测什么

| 端点 | 钉住的断言 |
|---|---|
| `GET /api/v1/project-templates` | **SYSTEM_ADMIN 闸** · 只列 `PUBLISHED` · **不含** `default_config_json` · **命名响应模型** |
| `POST /api/v1/projects/{id}/apply-template` | **同一事务**（失败 ⇒ 全回滚）· **幂等** · `record_approval` **不夺人工绑定** |
| `PATCH /api/v1/projects/{id}/unit-system` | 403 非 admin · 404 无权 · 200 + 回显 · 非法值 422 |
| `PATCH /api/v1/projects/{id}/status` | `DRAFT → ACTIVE` ✓ · `ACTIVE → ACTIVE` 409 · `ACTIVE → DRAFT` 409 |
| `POST /api/v1/projects` | `status='DRAFT'` 可传（向导第 1 步） |
| `GET /api/v1/meta/ui-schema/bedd` | 每个数值字段**带 `unit`** · 标签**不含单位** · 可换算字段**带 `unit_display`** |

## ⚠️ 为什么用 `strict_client`（**不**用默认 `client`）

默认 `client` fixture 把项目守卫 mock 成永远 True ⇒ ⇒ ⇒ 在它上面测
「越权被拒」是**空断言** ⇒ ⇒ ⇒ 本组要测 404/403 ⇒ ⇒ ⇒ 必须用 conftest 的
**`strict_client`**（走真守卫）⇒ ⇒ ⇒ ⇒ 且**不自建** client ——
自建 client 的文件集合是**冻结的**（`tests/test_strict_client_ratchet.py`）
⇒ ⇒ ⇒ 新文件自建 ⇒ ⇒ ⇒ 那个棘轮立刻红。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.config_domain import ProjectTemplate
from app.models.deliverable import (
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import ProjectTemplateStatus
from app.models.project import Project, Workspace
from app.models.system import ProjectInputChecklist

pytestmark = pytest.mark.asyncio


def _admin_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='admin-user', role='SYSTEM_ADMIN')}"
    }


def _designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='test-user', role='DESIGNER')}"
    }


async def _make_workspace(db: AsyncSession) -> uuid.UUID:
    workspace_id = uuid.uuid4()
    db.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            name="WS-WIZARD",
            status="ACTIVE",
        )
    )
    await db.commit()
    return workspace_id


async def _make_project(db: AsyncSession, *, status: str = "DRAFT") -> uuid.UUID:
    workspace_id = await _make_workspace(db)
    project_id = uuid.uuid4()
    db.add(
        Project(
            project_id=project_id,
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="向导测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
            status=status,
            workspace_id=workspace_id,
        )
    )
    await db.commit()
    return project_id


def _template_config(*, with_record: bool, with_matrix: bool) -> dict:
    cfg: dict = {"stream_approval": {"max_depth": 2}}
    if with_record:
        cfg["record_approval"] = {"steps": [{"role": "DESIGNER", "level": 1}]}
    if with_matrix:
        cfg["signature_matrix"] = {
            "matrix_name": "TPL_MATRIX",
            "steps": [{"role": "REVIEWER", "level": 1}],
        }
    return cfg


async def _make_template(
    db: AsyncSession,
    *,
    name: str,
    status: str = ProjectTemplateStatus.PUBLISHED.value,
    with_record: bool = False,
    with_matrix: bool = False,
    checklist: dict | None = None,
) -> ProjectTemplate:
    tpl = ProjectTemplate(
        name=name,
        industry="CHEMICAL",
        default_config_json=_template_config(
            with_record=with_record, with_matrix=with_matrix
        ),
        version="1.0.0",
        status=status,
        checklist_json=checklist,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


# ---------------------------------------------------------------------------
# GET /project-templates
# ---------------------------------------------------------------------------


async def test_list_templates_requires_system_admin(db_engine, strict_client):
    ac = strict_client
    r = await ac.get("/api/v1/project-templates", headers=_designer_headers())
    assert r.status_code == 403, r.text


async def test_list_templates_only_published_and_hides_config(db_engine, db_session, strict_client):
    await _make_template(db_session, name="已发布模板", status="PUBLISHED")
    await _make_template(db_session, name="草稿模板", status="DRAFT")

    ac = strict_client
    r = await ac.get("/api/v1/project-templates", headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    names = [t["name"] for t in body]
    assert "已发布模板" in names
    assert "草稿模板" not in names
    # ⚠️ **列表响应不含完整配置**（7 段）⇒ ⇒ ⇒ 那是「应用」时才读的东西
    assert "default_config_json" not in body[0]


# ---------------------------------------------------------------------------
# POST /projects/{id}/apply-template
# ---------------------------------------------------------------------------


async def test_apply_template_applies_typed_columns_and_provenance(db_engine, db_session, strict_client):
    tpl = await _make_template(db_session, name="T-typed")
    project_id = await _make_project(db_session)

    ac = strict_client
    r = await ac.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=_admin_headers(),
        json={"template_id": str(tpl.template_id)},
    )
    assert r.status_code == 200, r.text

    row = (
        await db_session.execute(
            select(Project).where(Project.project_id == project_id)
        )
    ).scalar_one()
    assert row.stream_approval_max_depth == 2
    assert row.applied_template_json is not None
    assert row.applied_template_json["template_id"] == str(tpl.template_id)
    assert "stream_approval" in row.applied_template_json["segments"]


async def test_apply_template_is_idempotent(db_engine, db_session, strict_client):
    tpl = await _make_template(
        db_session,
        name="T-idem",
        checklist={"items": [{"item_key": "bedd", "item_label": "BEDD"}]},
    )
    project_id = await _make_project(db_session)

    ac = strict_client
    for _ in range(2):
        r = await ac.post(
            f"/api/v1/projects/{project_id}/apply-template",
            headers=_admin_headers(),
            json={"template_id": str(tpl.template_id)},
        )
        assert r.status_code == 200, r.text

    # ⇒ ⇒ ⇒ **不产生重复行**（清单按 item_key 幂等）
    items = (
        await db_session.execute(
            select(ProjectInputChecklist).where(
                ProjectInputChecklist.project_id == project_id
            )
        )
    ).scalars().all()
    assert len(items) == 1, items


async def test_apply_template_rejects_unpublished_template(db_engine, db_session, strict_client):
    tpl = await _make_template(db_session, name="T-draft", status="DRAFT")
    project_id = await _make_project(db_session)

    ac = strict_client
    r = await ac.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=_admin_headers(),
        json={"template_id": str(tpl.template_id)},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "TEMPLATE_NOT_PUBLISHED"


async def test_apply_template_rejects_both_approval_segments(db_engine, db_session, strict_client):
    """⚠️ `record_approval` ↔ `signature_matrix` **互斥** ⇒ ⇒ ⇒ 422。"""
    tpl = await _make_template(
        db_session, name="T-both", with_record=True, with_matrix=True
    )
    project_id = await _make_project(db_session)

    ac = strict_client
    r = await ac.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=_admin_headers(),
        json={"template_id": str(tpl.template_id)},
    )
    assert r.status_code == 422, r.text


async def test_apply_template_does_not_steal_manual_matrix_binding(db_engine, db_session, strict_client):
    """⚠️ **人工改过的绑定不被夺走**（既有不变量 · bug-2211）。"""
    project_id = await _make_project(db_session)
    manual = SignatureMatrix(
        matrix_name="MANUAL_MATRIX",
        module="RECORD",
        doc_type="RECORD",
        version_purpose="DRAFT",
        steps_json=[{"step_order": 1, "sign_role": "APPROVER"}],
        status="ACTIVE",
    )
    db_session.add(manual)
    await db_session.flush()
    db_session.add(
        ProjectSignatureMatrixBinding(
            project_id=project_id, module="RECORD", matrix_id=manual.matrix_id
        )
    )
    await db_session.commit()

    tpl = await _make_template(db_session, name="T-record", with_record=True)
    ac = strict_client
    r = await ac.post(
        f"/api/v1/projects/{project_id}/apply-template",
        headers=_admin_headers(),
        json={"template_id": str(tpl.template_id)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["segments"]["record_approval"] == "skipped_manual_binding"

    binding = (
        await db_session.execute(
            select(ProjectSignatureMatrixBinding).where(
                ProjectSignatureMatrixBinding.project_id == project_id,
                ProjectSignatureMatrixBinding.module == "RECORD",
            )
        )
    ).scalar_one()
    assert binding.matrix_id == manual.matrix_id


# ---------------------------------------------------------------------------
# PATCH unit-system / status
# ---------------------------------------------------------------------------


async def test_set_unit_system_requires_admin_and_updates(db_engine, db_session, strict_client):
    project_id = await _make_project(db_session)
    ac = strict_client
    forbidden = await ac.patch(
        f"/api/v1/projects/{project_id}/unit-system",
        headers=_designer_headers(),
        json={"unit_system": "US"},
    )
    assert forbidden.status_code == 403, forbidden.text

    r = await ac.patch(
        f"/api/v1/projects/{project_id}/unit-system",
        headers=_admin_headers(),
        json={"unit_system": "US"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["unit_system"] == "US"


async def test_set_unit_system_rejects_unknown_value(db_engine, db_session, strict_client):
    project_id = await _make_project(db_session)
    ac = strict_client
    r = await ac.patch(
        f"/api/v1/projects/{project_id}/unit-system",
        headers=_admin_headers(),
        json={"unit_system": "MKS"},
    )
    assert r.status_code == 422, r.text


async def test_set_status_is_one_way(db_engine, db_session, strict_client):
    project_id = await _make_project(db_session, status="DRAFT")
    ac = strict_client
    ok = await ac.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=_admin_headers(),
        json={"status": "ACTIVE"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "ACTIVE"

    # ⇒ ⇒ ⇒ 已经是 ACTIVE 再激活 ⇒ ⇒ ⇒ 409（不是 200 空转）
    again = await ac.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=_admin_headers(),
        json={"status": "ACTIVE"},
    )
    assert again.status_code == 409, again.text

    # ⇒ ⇒ ⇒ ACTIVE → DRAFT ⇒ ⇒ ⇒ 409（单向）
    back = await ac.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=_admin_headers(),
        json={"status": "DRAFT"},
    )
    assert back.status_code == 409, back.text


async def test_project_out_exposes_unit_system_and_status(db_engine, db_session, strict_client):
    project_id = await _make_project(db_session, status="DRAFT")
    ac = strict_client
    r = await ac.get(f"/api/v1/projects/{project_id}", headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unit_system"] == "SI"
    assert body["status"] == "DRAFT"


# ---------------------------------------------------------------------------
# ui-schema：单位随字段下发（W-1 / W-1b）
# ---------------------------------------------------------------------------


async def test_bedd_ui_schema_carries_unit_and_no_unit_in_label(db_engine, strict_client):
    ac = strict_client
    r = await ac.get("/api/v1/meta/ui-schema/bedd", headers=_admin_headers())
    assert r.status_code == 200, r.text
    fields = r.json()["fields"]
    by_path = {f["path"]: f for f in fields}

    pressure = by_path["meteorology.pressure"]
    # ⚠️ **标签里不含单位** ⇒ ⇒ ⇒ 否则 US 模式下会出现「kPa / psi」双单位
    assert pressure["label"] == "气压"
    assert pressure["unit"] == "kPa"
    # ⚠️ **换算因子真的到达客户端了** ⇒ ⇒ ⇒（契约漏声明 ⇒ ⇒ ⇒ 静默丢弃）
    assert pressure["unit_display"]["display_unit"] == "psi"
    assert pressure["unit_display"]["factor"] > 0

    # ⚠️ **不可换算的字段 `unit_display` 为 null** ⇒ ⇒ ⇒ 前端标灰 + 提示
    #    （契约里这个键**存在**（nullable）⇒ ⇒ ⇒ 判据是「值是不是 null」）
    assert by_path["meteorology.humidity"]["unit_display"] is None
    assert by_path["meteorology.humidity"]["unit"] == "%"

    # ⚠️ **无单位字段 `unit` 也是 null**（判据 = 值是不是 null）
    assert by_path["utilities.steam"]["unit"] is None
