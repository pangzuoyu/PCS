"""ConfigStateMachine 5 态骨架测试（Task 1.2）。

Schema 适应：
- `asset.current_version` 是 String(50) 列，不是 ConfigVersion 关系；
  测试通过 make_asset bundle 显式取得 version 对象传给 transition()。
- 测试断言 `asset.status`（状态机唯一可变字段），不遍历 .content_json/.approvals。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.enums import ConfigStatus, ConfigTransition
from app.models.system import AuditLog
from app.services.config_state_machine import (
    ConfigStateMachine,
    InvalidTransitionError,
)

pytestmark = pytest.mark.asyncio


async def test_draft_to_pending_writes_audit(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.DRAFT.value)
    sm = ConfigStateMachine(db)
    await sm.transition(
        bundle.asset,
        bundle.version,
        action=ConfigTransition.SUBMIT,
        actor=actor,
    )
    await db.commit()
    assert bundle.asset.status == ConfigStatus.PENDING.value
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(bundle.asset.asset_id)
            )
        )
    ).scalar_one()
    assert audit.action == "CONFIG_ASSET_SUBMITTED"


async def test_pending_to_approved_single_writes_audit(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.PENDING.value, category="CATEGORY_3")
    sm = ConfigStateMachine(db)
    await sm.transition(
        bundle.asset,
        bundle.version,
        action=ConfigTransition.APPROVE,
        actor=actor,
        role="PROCESS_CONTROLLER",
    )
    await db.commit()
    assert bundle.asset.status == ConfigStatus.APPROVED.value
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(bundle.asset.asset_id)
            )
        )
    ).scalar_one()
    assert audit.action == "CONFIG_ASSET_APPROVED"


async def test_pending_to_draft_on_reject_writes_audit(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.PENDING.value)
    sm = ConfigStateMachine(db)
    await sm.transition(
        bundle.asset,
        bundle.version,
        action=ConfigTransition.REJECT,
        actor=actor,
    )
    await db.commit()
    assert bundle.asset.status == ConfigStatus.DRAFT.value
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(bundle.asset.asset_id)
            )
        )
    ).scalar_one()
    assert audit.action == "CONFIG_ASSET_REJECTED"


async def test_approved_to_published_writes_audit(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.APPROVED.value)
    sm = ConfigStateMachine(db)
    await sm.transition(
        bundle.asset,
        bundle.version,
        action=ConfigTransition.PUBLISH,
        actor=actor,
    )
    await db.commit()
    assert bundle.asset.status == ConfigStatus.PUBLISHED.value
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(bundle.asset.asset_id)
            )
        )
    ).scalar_one()
    assert audit.action == "CONFIG_ASSET_PUBLISHED"


async def test_published_to_obsolete_writes_audit(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.PUBLISHED.value)
    sm = ConfigStateMachine(db)
    await sm.transition(
        bundle.asset,
        bundle.version,
        action=ConfigTransition.OBSOLETE,
        actor=actor,
    )
    await db.commit()
    assert bundle.asset.status == ConfigStatus.OBSOLETE.value
    audit = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(bundle.asset.asset_id)
            )
        )
    ).scalar_one()
    assert audit.action == "CONFIG_ASSET_OBSOLETED"


async def test_invalid_transition_raises(db, make_asset, actor):
    bundle = await make_asset(status=ConfigStatus.DRAFT.value)
    sm = ConfigStateMachine(db)
    with pytest.raises(InvalidTransitionError):
        await sm.transition(
            bundle.asset,
            bundle.version,
            action=ConfigTransition.PUBLISH,
            actor=actor,
        )
