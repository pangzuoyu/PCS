"""项目产品类别 API (product_category, GB 30251-2024 §6.1.5 电折标口径判据).

用户裁决 2026-10-05「按 project 产品类型强制」之后发现:
PCS **没有 Project create API** (`user_projects.py` 只做访问授权/查询,
`workspaces.py` 只管 workspace) → product_category 只能在 DB/seed 层设置,
真实项目运维成本高。

本测试锁定最小可用面:
    GET   /projects/{project_id}                        读项目 + 生效的电折标口径
    PATCH /projects/{project_id}/product-category       设产品类别 (SYSTEM_ADMIN)
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace
from app.models.util import UtilityEnergySummary


async def _make_project(
    db: AsyncSession, *, product_category: str = "OTHER"
) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    db.add(Workspace(workspace_id=workspace_id, workspace_type="FORMAL", name="WS"))
    project_id = uuid.uuid4()
    db.add(
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
            product_category=product_category,
        )
    )
    await db.commit()
    return project_id, workspace_id


@pytest.fixture
def admin_headers() -> dict:
    """SYSTEM_ADMIN header — 走 conftest 的 create_access_token 路径 (P1 mock_auth 解码)."""
    return {
        "Authorization": f"Bearer {create_access_token(subject='admin-user', role='SYSTEM_ADMIN')}"
    }


@pytest.fixture
def designer_headers() -> dict:
    """DESIGNER header — 与 conftest sample_user_token 同路径."""
    return {
        "Authorization": f"Bearer {create_access_token(subject='test-user', role='DESIGNER')}"
    }


# ---------------------------------------------------------------------------
# GET /projects/{project_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project_exposes_product_category(
    client, db_session, admin_headers
):
    project_id, _ws = await _make_project(db_session, product_category="REFINING")
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["product_category"] == "REFINING"
    # 电折标口径应随产品类别一并暴露, 便于运维核对 (不必读代码推导)
    assert body["electricity_value_type"] == "EQUIVALENT_VALUE"


@pytest.mark.asyncio
async def test_get_project_other_uses_equivalent(
    client, db_session, admin_headers
):
    project_id, _ws = await _make_project(db_session, product_category="OTHER")
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["electricity_value_type"] == "EQUIVALENT"


# ---------------------------------------------------------------------------
# PATCH /projects/{project_id}/product-category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_product_category_requires_admin(
    client, db_session, designer_headers
):
    project_id, _ws = await _make_project(db_session)
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/product-category",
        json={"product_category": "REFINING"},
        headers=designer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_product_category_sets_refining(
    client, db_session, admin_headers
):
    project_id, _ws = await _make_project(db_session, product_category="OTHER")
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/product-category",
        json={"product_category": "REFINING"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["product_category"] == "REFINING"
    assert resp.json()["electricity_value_type"] == "EQUIVALENT_VALUE"
    row = (
        await db_session.execute(
            select(Project).where(Project.project_id == project_id)
        )
    ).scalar_one()
    await db_session.refresh(row)
    assert row.product_category == "REFINING"


@pytest.mark.asyncio
async def test_patch_product_category_rejects_invalid_value(
    client, db_session, admin_headers
):
    project_id, _ws = await _make_project(db_session)
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/product-category",
        json={"product_category": "REFININGGG"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_product_category_blocked_when_summaries_exist(
    client, db_session, admin_headers
):
    """已有综合能耗汇总时改产品类别 ⇒ 422.

    理由: 每条 UtilityEnergySummary 都固化了当时的 electricity_value_type,
    改项目类别会让历史汇总与新口径不一致且无法追溯 ⇒ fail-closed, 拒绝。
    """
    project_id, workspace_id = await _make_project(db_session)
    db_session.add(
        UtilityEnergySummary(
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=2026,
            source="CALCULATION",
            electricity_kwh_yr=1000.0,
            annual_total_energy=3600.0,
            toe_conversion_factor=1e-9,
            standard_coal_factor=1e-9,
            total_toe=0.086,
            total_standard_coal_kg=0.1229,
            electricity_value_type="EQUIVALENT",
        )
    )
    await db_session.commit()
    resp = await client.patch(
        f"/api/v1/projects/{project_id}/product-category",
        json={"product_category": "REFINING"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
    # PCS 错误信封是扁平的 (code/message 在顶层, 非 detail 下)
    body = resp.json()
    assert body["code"] == "PRODUCT_CATEGORY_LOCKED"
    assert "汇总" in body["message"]


@pytest.mark.asyncio
async def test_patch_product_category_not_found(
    client, db_session, admin_headers
):
    resp = await client.patch(
        f"/api/v1/projects/{uuid.uuid4()}/product-category",
        json={"product_category": "REFINING"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
