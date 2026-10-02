"""F-P2-009 Sprint 3: Audit Query 后端测试 (Issue 5 错误路径 + Issue 7 混合 RBAC).

覆盖:
- /audit-logs: SYSTEM_ADMIN only, 9-dim filter
- /equipment-deletion-audit: DESIGNER+ + project_id filter (F-P0-004 IDOR)
- /config-audit: DESIGNER+ (公司级全局, 无 project 隔离)

参考: docs/sprint3-plan-2026-10-02.md Issue 5/7.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from app.core.security import create_access_token
from app.models.equipment import EquipmentDeletionAudit
from app.models.system import AuditLog

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Token fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_token() -> str:
    return create_access_token(subject="admin-user", role="SYSTEM_ADMIN")


@pytest.fixture
def designer_token() -> str:
    return create_access_token(subject="designer-user", role="DESIGNER")


@pytest.fixture
def pc_token() -> str:
    return create_access_token(subject="pc-user", role="PROCESS_CONTROLLER")


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------


async def _insert_audit_log(
    db,
    *,
    user_id: uuid.UUID | None = None,
    action: str = "TEST_ACTION",
    resource_type: str = "test_resource",
    resource_id: str = "res-001",
    detail_json: dict | None = None,
    occurred_at: datetime | None = None,
):
    """直接 INSERT 一行 audit_logs (测试 fixture 简化)."""
    row = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=detail_json or {},
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


async def _insert_equipment_deletion_audit(
    db,
    *,
    project_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    equipment_id: uuid.UUID | None = None,
    equipment_tag: str = "E-001",
    deleted_by: uuid.UUID | None = None,
    orphan_records: dict | None = None,
):
    row = EquipmentDeletionAudit(
        project_id=project_id or uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        equipment_id=equipment_id or uuid.uuid4(),
        equipment_tag=equipment_tag,
        deleted_by=deleted_by or uuid.uuid4(),
        orphan_records=orphan_records or {},
    )
    db.add(row)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# /audit-logs
# ---------------------------------------------------------------------------


class TestAuditLogsEndpoint:
    """/audit-logs: SYSTEM_ADMIN only + 9-dim filter."""

    async def test_unauthenticated_401(self, client):
        r = await client.get("/api/v1/audit-logs")
        assert r.status_code in (401, 403), r.text

    async def test_designer_forbidden_403(self, client, designer_token):
        """DESIGNER 访问 /audit-logs → 403 (Issue 7 RBAC 收窄)."""
        r = await client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 403, r.text

    async def test_admin_list_empty(self, client, admin_token):
        """SYSTEM_ADMIN 访问 → 200 + 空列表."""
        r = await client.get(
            "/api/v1/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_admin_filter_resource_type_config_energy(
        self, client, db, admin_token
    ):
        """filter resource_type=config_energy_conversion_factors (F-P0-001 R1)."""
        await _insert_audit_log(
            db, action="CONFIG_R1_BACKFILL",
            resource_type="config_energy_conversion_factors",
            resource_id="1",
        )
        await _insert_audit_log(
            db, action="OTHER", resource_type="equipment_list",
        )
        await db.commit()

        r = await client.get(
            "/api/v1/audit-logs",
            params={"resource_type": "config_energy_conversion_factors"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "CONFIG_R1_BACKFILL"
        assert body["items"][0]["resource_type"] == "config_energy_conversion_factors"

    async def test_admin_filter_user_id(self, client, db, admin_token):
        """filter user_id=X → 只返回该 user 的 audit."""
        target_user = uuid.uuid4()
        await _insert_audit_log(db, user_id=target_user, action="TARGET_ACTION")
        await _insert_audit_log(db, user_id=uuid.uuid4(), action="OTHER_ACTION")
        await db.commit()

        r = await client.get(
            "/api/v1/audit-logs",
            params={"user_id": str(target_user)},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "TARGET_ACTION"

    async def test_limit_out_of_range_422(self, client, admin_token):
        """limit=0 → 422 (FastAPI ge=1 校验)."""
        r = await client.get(
            "/api/v1/audit-logs",
            params={"limit": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 422, r.text

    async def test_pagination_limit_offset(self, client, db, admin_token):
        """limit=10 offset=5 分页."""
        for i in range(15):
            await _insert_audit_log(db, resource_id=f"r-{i:03d}")
        await db.commit()

        r = await client.get(
            "/api/v1/audit-logs",
            params={"limit": 10, "offset": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 15
        assert len(body["items"]) == 10
        assert len(body["items"]) == 10


# ---------------------------------------------------------------------------
# /equipment-deletion-audit
# ---------------------------------------------------------------------------


class TestEquipmentDeletionAuditEndpoint:
    """/equipment-deletion-audit: DESIGNER+ + project_id filter (F-P0-004 IDOR)."""

    async def test_designer_requires_project_id_403(self, client, designer_token):
        """非 admin 不传 project_id → 403."""
        r = await client.get(
            "/api/v1/equipment-deletion-audit",
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 403, r.text

    async def test_designer_own_project_200(self, client, db, designer_token):
        """DESIGNER + 自己 project_id → 200."""
        project_id = uuid.uuid4()
        await _insert_equipment_deletion_audit(
            db, project_id=project_id, equipment_tag="E-OWN-001",
        )
        await db.commit()

        r = await client.get(
            "/api/v1/equipment-deletion-audit",
            params={"project_id": str(project_id)},
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1

    async def test_designer_other_project_empty(
        self, client, db, designer_token
    ):
        """DESIGNER 传 project_id=X, 但 audit 在 Y → 空 items (IDOR 防护).

        实际: 后端应按 project_id 过滤, DESIGNER 传 X 即使有 Y 的数据也看不到.
        测试场景: DB 只有 project_Y 的 audit, DESIGNER 请求 project_X → 0 items.
        """
        other_project = uuid.uuid4()
        await _insert_equipment_deletion_audit(
            db, project_id=other_project, equipment_tag="E-OTHER-001",
        )
        await db.commit()

        target_project = uuid.uuid4()
        r = await client.get(
            "/api/v1/equipment-deletion-audit",
            params={"project_id": str(target_project)},
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_admin_no_project_filter_sees_all(
        self, client, db, admin_token
    ):
        """SYSTEM_ADMIN 不传 project_id → 看全部."""
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        await _insert_equipment_deletion_audit(db, project_id=p1)
        await _insert_equipment_deletion_audit(db, project_id=p2)
        await db.commit()

        r = await client.get(
            "/api/v1/equipment-deletion-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2


# ---------------------------------------------------------------------------
# /config-audit
# ---------------------------------------------------------------------------


class TestConfigAuditEndpoint:
    """/config-audit: DESIGNER+ (公司级全局, 无 project 隔离, Issue 7)."""

    async def test_unauthenticated_401(self, client):
        r = await client.get("/api/v1/config-audit")
        assert r.status_code in (401, 403), r.text

    async def test_designer_no_filter_returns_config_audit(
        self, client, db, designer_token
    ):
        """DESIGNER 不传 asset_id → 全公司 config_energy_conversion_factors audit."""
        await _insert_audit_log(
            db, action="CONFIG_R1_BACKFILL",
            resource_type="config_energy_conversion_factors",
            resource_id="42",
        )
        await _insert_audit_log(
            db, action="OTHER", resource_type="equipment_list",
        )
        await db.commit()

        r = await client.get(
            "/api/v1/config-audit",
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["resource_type"] == "config_energy_conversion_factors"

    async def test_designer_filter_asset_id(
        self, client, db, designer_token
    ):
        """DESIGNER 传 asset_id=42 → 只返回 resource_id=42 的 audit."""
        await _insert_audit_log(
            db, action="R1_REVISION",
            resource_type="config_energy_conversion_factors",
            resource_id="42",
        )
        await _insert_audit_log(
            db, action="OTHER_REVISION",
            resource_type="config_energy_conversion_factors",
            resource_id="99",
        )
        await db.commit()

        r = await client.get(
            "/api/v1/config-audit",
            params={"asset_id": 42},
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["resource_id"] == "42"

    async def test_asset_id_nonexistent_returns_empty(
        self, client, db, designer_token
    ):
        """asset_id 不存在 → 空 items (不是 404, list 端点)."""
        await _insert_audit_log(
            db, resource_type="config_energy_conversion_factors",
            resource_id="999",
        )
        await db.commit()

        r = await client.get(
            "/api/v1/config-audit",
            params={"asset_id": 12345},
            headers={"Authorization": f"Bearer {designer_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 0