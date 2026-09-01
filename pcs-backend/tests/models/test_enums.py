"""AuditAction 枚举测试：CONFIG_* 8 项（P2 Sprint 1.1）。"""

from __future__ import annotations

from app.models.enums import AuditAction


def test_config_audit_actions_exist():
    """P2 Sprint 1.1：CONFIG_* 8 项枚举值追加。"""
    assert AuditAction.CONFIG_ASSET_CREATED.value == "CONFIG_ASSET_CREATED"
    assert AuditAction.CONFIG_VERSION_CREATED.value == "CONFIG_VERSION_CREATED"
    assert AuditAction.CONFIG_ASSET_SUBMITTED.value == "CONFIG_ASSET_SUBMITTED"
    assert AuditAction.CONFIG_ASSET_APPROVED.value == "CONFIG_ASSET_APPROVED"
    assert AuditAction.CONFIG_ASSET_PUBLISHED.value == "CONFIG_ASSET_PUBLISHED"
    assert AuditAction.CONFIG_ASSET_OBSOLETED.value == "CONFIG_ASSET_OBSOLETED"
    assert AuditAction.CONFIG_ASSET_REJECTED.value == "CONFIG_ASSET_REJECTED"
    assert AuditAction.CONFIG_VERSION_DIFF_VIEWED.value == "CONFIG_VERSION_DIFF_VIEWED"
    # 既有 39 项 + 本次新增 8 项
    assert len(list(AuditAction)) >= 8 + 39