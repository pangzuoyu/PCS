"""Audit 测试：AuditAction 长度 + AuditService 写入。"""

from __future__ import annotations

import pytest

from app.models.enums import AuditAction

pytestmark = pytest.mark.asyncio


def test_audit_action_max_length_50():
    """Issue 6 锁定：AuditAction 全部 ≤50 字符（DB String(50)）。"""
    max_len = max(len(a.value) for a in AuditAction)
    assert max_len <= 50, f"最长值 {max_len} 字符：超 DB 限制"


def test_audit_action_contains_p0_p1_required():
    expected = {
        "LOGIN_SUCCESS",
        "LOGOUT",
        "WORKSPACE_CREATED",
        "WORKSPACE_CLEANED",
        "CHECKLIST_ITEM_VERIFIED",
        "CHECKLIST_COMPLETENESS_BLOCKED",
        "SNAPSHOT_CREATED",
        "CIA_NOTIFIED",
        "RECORD_TRANSITION",
    }
    actual = {a.value for a in AuditAction}
    missing = expected - actual
    assert not missing, f"缺失：{missing}"


def test_audit_action_no_duplicate_values():
    values = [a.value for a in AuditAction]
    assert len(values) == len(set(values)), "枚举值有重复"


async def test_audit_service_writes_one_row(db_session):
    import uuid

    from app.services.audit_service import AuditService

    svc = AuditService(db_session)
    actor = uuid.uuid4()
    entry = await svc.write(
        action=AuditAction.WORKSPACE_CREATED,
        resource_type="workspaces",
        resource_id=actor,
        user_id=actor,
        detail={"name": "test"},
    )
    assert entry.audit_id is not None
    assert entry.action == "WORKSPACE_CREATED"
    assert entry.resource_type == "workspaces"
    await db_session.commit()


async def test_audit_service_truncates_long_resource_type(db_session):
    import uuid

    from app.services.audit_service import AuditService

    svc = AuditService(db_session)
    entry = await svc.write(
        action=AuditAction.READ,
        resource_type="x" * 200,
        resource_id=uuid.uuid4(),
    )
    assert len(entry.resource_type) == 50