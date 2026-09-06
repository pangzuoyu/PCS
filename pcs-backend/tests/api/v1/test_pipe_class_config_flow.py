"""SUP-002 PC-3: 管道等级 + ConfigAsset 5 态接入（V1.4 §0.5/§2.1/§3.1）。

覆盖：
1. test_create_creates_config_asset    POST 201 DB 查 ConfigAsset 挂 PIPE_CLASS
2. test_submit_draft_to_pending         DRAFT submit PENDING
3. test_approve_pending_to_approved     PENDING approve APPROVED（CATEGORY_5 单层签）
4. test_publish_updates_mirror_status   完整 DRAFT→PENDING→APPROVED→PUBLISHED
5. test_invalid_transition_rejected     PENDING 直接 publish 返回 409
6. test_obsolete_from_published         PUBLISHED obsolete OBSOLETE

契约要点（V1.4）：
- POST /pipe-classes 同时创建 PipeClass（DRAFT）+ ConfigAsset + ConfigVersion v1
- pipe_classes.asset_id 反向指 ConfigAsset；pipe_classes.status 是 ConfigAsset.status 镜像
- pipe_classes.status ∈ {DRAFT, PENDING, APPROVED, PUBLISHED, OBSOLETE}
- /approve 走 record_approval（CATEGORY_5 单层签）；/submit/publish/obsolete 走 transition

ACL（写作计划 §PC-3）：
- POST /pipe-classes        : PROCESS_CONTROLLER / SYSTEM_ADMIN
- /submit                   : PROCESS_CONTROLLER / SYSTEM_ADMIN
- /approve                  : REVIEWER / SYSTEM_ADMIN
- /publish                  : APPROVER / SYSTEM_ADMIN
- /obsolete                 : PROCESS_CONTROLLER / REVIEWER / APPROVER / SYSTEM_ADMIN
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.config_domain import ConfigAsset, ConfigVersion, PipeClass

_BODY = {
    "class_id": "A1",
    "class_name": "管道等级 A1",
    "material_standard": "GB/T 8163",
    "corrosion_allowance": 1.5,
    "design_pressure": 2.5,
    "design_temperature": 200.0,
    "dn_series_json": {"min": 15, "max": 350},
    "sch_series_json": {"15": "40", "350": "STD"},
    "flange_class": "PN25",
    "source": "COMPANY_STD",
    "version": "PC-V1.0",
}


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _reviewer_token() -> str:
    return create_access_token(subject="test-reviewer", role="REVIEWER")


def _approver_token() -> str:
    return create_access_token(subject="test-approver", role="APPROVER")


async def _create_via_api(client, sample_pc_token) -> dict:
    """POST → 201；返回 response JSON。"""
    r = await client.post("/api/v1/pipe-classes", json=_BODY, headers=_bearer(sample_pc_token))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. POST → ConfigAsset 挂 PIPE_CLASS（CATEGORY_5）
# ---------------------------------------------------------------------------


async def test_create_creates_config_asset(client, sample_pc_token, db):
    """POST /pipe-classes 同步创建 ConfigAsset(CATEGORY_5/asset_subtype=PIPE_CLASS)。"""
    body = await _create_via_api(client, sample_pc_token)
    assert body["class_id"] == "A1"
    assert body["status"] == "DRAFT"

    pc = await db.get(PipeClass, "A1")
    assert pc is not None
    assert pc.asset_id is not None, "PC-3 必须挂 ConfigAsset"

    asset = await db.get(ConfigAsset, pc.asset_id)
    assert asset is not None
    assert asset.category == "CATEGORY_5"
    assert asset.asset_subtype == "PIPE_CLASS"
    assert asset.status == "DRAFT"
    assert asset.name == "管道等级 A1"

    # ConfigVersion v1 同步建立（双段签 API 要求）
    versions = (
        await db.execute(
            select(ConfigVersion).where(ConfigVersion.asset_id == asset.asset_id)
        )
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].status == "DRAFT"


# ---------------------------------------------------------------------------
# 2. submit：DRAFT → PENDING
# ---------------------------------------------------------------------------


async def test_submit_draft_to_pending(client, sample_pc_token, db):
    await _create_via_api(client, sample_pc_token)
    r = await client.post(
        "/api/v1/pipe-classes/A1/submit", headers=_bearer(sample_pc_token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PENDING"

    # 镜像列同步
    pc = await db.get(PipeClass, "A1")
    assert pc.status == "PENDING"
    asset = await db.get(ConfigAsset, pc.asset_id)
    assert asset.status == "PENDING"


# ---------------------------------------------------------------------------
# 3. approve：PENDING → APPROVED（CATEGORY_5 单层签）
# ---------------------------------------------------------------------------


async def test_approve_pending_to_approved(client, sample_pc_token, db):
    await _create_via_api(client, sample_pc_token)
    r = await client.post(
        "/api/v1/pipe-classes/A1/submit", headers=_bearer(sample_pc_token)
    )
    assert r.status_code == 200

    r = await client.post(
        "/api/v1/pipe-classes/A1/approve", headers=_bearer(_reviewer_token())
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"

    pc = await db.get(PipeClass, "A1")
    assert pc.status == "APPROVED"


# ---------------------------------------------------------------------------
# 4. publish：完整链路 + mirror-status
# ---------------------------------------------------------------------------


async def test_publish_updates_mirror_status(client, sample_pc_token, db):
    await _create_via_api(client, sample_pc_token)
    r = await client.post("/api/v1/pipe-classes/A1/submit", headers=_bearer(sample_pc_token))
    assert r.status_code == 200
    r = await client.post("/api/v1/pipe-classes/A1/approve", headers=_bearer(_reviewer_token()))
    assert r.status_code == 200
    r = await client.post("/api/v1/pipe-classes/A1/publish", headers=_bearer(_approver_token()))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PUBLISHED"

    pc = await db.get(PipeClass, "A1")
    assert pc.status == "PUBLISHED"
    asset = await db.get(ConfigAsset, pc.asset_id)
    assert asset.status == "PUBLISHED"


# ---------------------------------------------------------------------------
# 5. 非法转移：PENDING 直接 publish → 409
# ---------------------------------------------------------------------------


async def test_invalid_transition_rejected(client, sample_pc_token):
    await _create_via_api(client, sample_pc_token)
    r = await client.post("/api/v1/pipe-classes/A1/submit", headers=_bearer(sample_pc_token))
    assert r.status_code == 200
    # PENDING 不允许 publish（仅 APPROVED→PUBLISHED）
    r = await client.post(
        "/api/v1/pipe-classes/A1/publish", headers=_bearer(_approver_token())
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# 6. obsolete：PUBLISHED → OBSOLETE
# ---------------------------------------------------------------------------


async def test_obsolete_from_published(client, sample_pc_token, db):
    await _create_via_api(client, sample_pc_token)
    await client.post("/api/v1/pipe-classes/A1/submit", headers=_bearer(sample_pc_token))
    await client.post("/api/v1/pipe-classes/A1/approve", headers=_bearer(_reviewer_token()))
    await client.post("/api/v1/pipe-classes/A1/publish", headers=_bearer(_approver_token()))

    r = await client.post(
        "/api/v1/pipe-classes/A1/obsolete", headers=_bearer(_reviewer_token())
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "OBSOLETE"

    pc = await db.get(PipeClass, "A1")
    assert pc.status == "OBSOLETE"