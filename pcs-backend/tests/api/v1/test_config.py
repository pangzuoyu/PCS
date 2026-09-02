"""Config API 端点测试（Task 2.8 — P2 Sprint 1.7）。

覆盖 7 端点 × (happy + 1 failure) = 16 测试。

防御性偏差（与 brief）：
1. fixture 注入使用 `client` + `sample_*_token`（已由 tests/conftest.py 提供），
   不重新声明。
2. `sample_two_version_asset` 仅返回 ConfigAsset；为获取 version_id，本测试
   显式查询 ConfigVersion（ConfigAsset.versions 关系不在 P1 schema 中）。
3. brief 的 `user.user_id` / `user.primary_role` 在项目中不存在 — 由 `config.py`
   的 `current_actor` 依赖暴露该字段。
4. 错误响应字段名：`r.json()["detail"]` 在本项目里实际是 None（HTTPException
   handler 把 exc.detail 放到 `message` 字段）。本测试断言改为 `["message"]`。
5. `test_obsolete_draft_returns_409` 改为 `test_obsolete_pending_returns_409`：
   P2 Sprint 1.2 锁定 5 态骨架 `DRAFT、APPROVED 可经 OBSOLETE 直接出局`，
   DRAFT→OBSOLETE 是合法转移；PENDING→OBSOLETE 才返回 409。
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.config_domain import ConfigVersion

# ---------------------------------------------------------------------------
# POST /assets
# ---------------------------------------------------------------------------


async def test_create_asset_returns_draft(client, sample_user_token):
    r = await client.post(
        "/api/v1/config/assets",
        json={"category": "CATEGORY_2", "name": "摩擦系数公式"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"


async def test_create_asset_missing_name_returns_422(client, sample_user_token):
    r = await client.post(
        "/api/v1/config/assets",
        json={"category": "CATEGORY_2"},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /assets/{id}/versions
# ---------------------------------------------------------------------------


async def test_create_version_for_draft_asset(
    client, sample_user_token, sample_draft_asset
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/versions",
        json={"content_json": {"expression": "a + b"}},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"


async def test_create_version_on_published_asset_returns_409(
    client, sample_user_token, sample_published_asset
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/versions",
        json={"content_json": {}},
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409
    assert "fork" in r.json()["message"]


# ---------------------------------------------------------------------------
# POST /assets/{id}/submit
# ---------------------------------------------------------------------------


async def test_submit_draft_to_pending(client, sample_user_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/submit",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PENDING"


async def test_submit_pending_asset_returns_409(
    client, sample_user_token, sample_pending_asset
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset.asset_id}/submit",
        headers={"Authorization": f"Bearer {sample_user_token}"},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /assets/{id}/approve
# ---------------------------------------------------------------------------


async def test_approve_pending_single_signoff(
    client, sample_pc_token, sample_pending_asset_c3
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset_c3.asset_id}/approve",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"


async def test_approve_requires_process_controller(
    client, sample_designer_token, sample_pending_asset_c3
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset_c3.asset_id}/approve",
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /assets/{id}/publish
# ---------------------------------------------------------------------------


async def test_publish_approved_with_passing_formula(
    client, sample_pc_token, sample_approved_formula_asset
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_approved_formula_asset.asset_id}/publish",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PUBLISHED"


async def test_publish_fails_when_unit_tests_incomplete(
    client, sample_pc_token, sample_approved_formula_with_failing_test
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_approved_formula_with_failing_test.asset_id}/publish",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 422
    assert "unit_tests" in r.json()["message"]


# ---------------------------------------------------------------------------
# POST /assets/{id}/obsolete
# ---------------------------------------------------------------------------


async def test_obsolete_published(client, sample_pc_token, sample_published_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/obsolete",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "OBSOLETE"


async def test_obsolete_pending_returns_409(
    client, sample_pc_token, sample_pending_asset
):
    """PENDING→OBSOLETE 非法（仅 DRAFT/APPROVED/PUBLISHED 可经 OBSOLETE 转移）。

    brief 原 `test_obsolete_draft_returns_409` 与状态机骨架冲突 ——
    P2 Sprint 1.2 锁定 DRAFT 可经 OBSOLETE 直接出局，本测试改用 PENDING
    样本以保持「non-allowed transition → 409」的语义覆盖。
    """
    r = await client.post(
        f"/api/v1/config/assets/{sample_pending_asset.asset_id}/obsolete",
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /assets/{id}/fork
# ---------------------------------------------------------------------------


async def test_fork_published_creates_draft(
    client, sample_pc_token, sample_published_asset
):
    r = await client.post(
        f"/api/v1/config/assets/{sample_published_asset.asset_id}/fork",
        json={"change_note": "修订摩擦因子"},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "DRAFT"
    assert r.json()["parent_version_id"] is not None


async def test_fork_draft_returns_409(client, sample_pc_token, sample_draft_asset):
    r = await client.post(
        f"/api/v1/config/assets/{sample_draft_asset.asset_id}/fork",
        json={},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# GET /assets/{id}/diff
# ---------------------------------------------------------------------------


async def test_diff_two_versions_returns_delta(
    client, sample_pc_token, sample_two_version_asset, db
):
    asset = sample_two_version_asset
    versions = (
        await db.execute(
            select(ConfigVersion)
            .where(ConfigVersion.asset_id == asset.asset_id)
            .order_by(ConfigVersion.version_code)
        )
    ).scalars().all()
    assert len(versions) >= 2
    vid1, vid2 = str(versions[0].version_id), str(versions[1].version_id)
    r = await client.get(
        f"/api/v1/config/assets/{asset.asset_id}/diff",
        params={"v1": vid1, "v2": vid2},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "added" in body or "changed" in body


async def test_diff_same_version_returns_400(
    client, sample_pc_token, sample_two_version_asset, db
):
    asset = sample_two_version_asset
    version = (
        await db.execute(
            select(ConfigVersion).where(ConfigVersion.asset_id == asset.asset_id)
        )
    ).scalars().first()
    vid = str(version.version_id)
    r = await client.get(
        f"/api/v1/config/assets/{asset.asset_id}/diff",
        params={"v1": vid, "v2": vid},
        headers={"Authorization": f"Bearer {sample_pc_token}"},
    )
    assert r.status_code == 400