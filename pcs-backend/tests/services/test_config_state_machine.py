"""ConfigStateMachine 5 态骨架测试（Task 1.2）+ 双段签测试（Task 1.3）。

Schema 适应：
- `asset.current_version` 是 String(50) 列，不是 ConfigVersion 关系；
  测试通过 make_asset bundle 显式取得 version 对象传给 transition()。
- 测试断言 `asset.status`（状态机唯一可变字段），不遍历 .content_json/.approvals。
- Task 1.3 双段签：调用 `sm.record_approval(asset, version, ...)` 实例方法，
  适配 _ActorLike Protocol（duck-typed，仅需 user_id）。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.config_domain import ConfigApproval
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


# === Task 1.3：双重审批通过双行 config_approvals 表达（D20 一致）===


async def test_double_signoff_full_approve(db, make_asset, actor):
    """CATEGORY_2 双段签：第 1 行 PROCESS_CONTROLLER 批准后仍 PENDING；
    第 2 行 SYSTEM_ADMIN 批准后转 APPROVED。"""
    bundle = await make_asset(
        status=ConfigStatus.PENDING.value, category="CATEGORY_2"
    )
    asset = bundle.asset
    version = bundle.version
    sm = ConfigStateMachine(db)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # 第一段签：PROCESS_CONTROLLER 批准
    await sm.record_approval(
        asset,
        version,
        approver_id=user_a,
        role="PROCESS_CONTROLLER",
        decision="APPROVED",
        actor=actor,
    )
    assert asset.status == ConfigStatus.PENDING.value

    # 第二段签：SYSTEM_ADMIN 批准 → 进 APPROVED
    await sm.record_approval(
        asset,
        version,
        approver_id=user_b,
        role="SYSTEM_ADMIN",
        decision="APPROVED",
        actor=actor,
    )
    assert asset.status == ConfigStatus.APPROVED.value
    await db.commit()

    # 验证 config_approvals 双行均落库
    approvals = (
        await db.execute(
            select(ConfigApproval).where(
                ConfigApproval.version_id == version.version_id
            )
        )
    ).scalars().all()
    assert len(approvals) == 2
    decisions = {a.approver_role: a.decision for a in approvals}
    assert decisions["PROCESS_CONTROLLER"] == "APPROVED"
    assert decisions["SYSTEM_ADMIN"] == "APPROVED"


async def test_double_signoff_any_reject_returns_to_draft(db, make_asset, actor):
    """CATEGORY_2 双段签：先 APPROVED 再 REJECTED → 回 DRAFT（任一驳回即回 DRAFT）。"""
    bundle = await make_asset(
        status=ConfigStatus.PENDING.value, category="CATEGORY_2"
    )
    asset = bundle.asset
    version = bundle.version
    sm = ConfigStateMachine(db)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # 第一段签：通过
    await sm.record_approval(
        asset,
        version,
        approver_id=user_a,
        role="PROCESS_CONTROLLER",
        decision="APPROVED",
        actor=actor,
    )
    # 第二段签：驳回
    await sm.record_approval(
        asset,
        version,
        approver_id=user_b,
        role="SYSTEM_ADMIN",
        decision="REJECTED",
        actor=actor,
    )
    assert asset.status == ConfigStatus.DRAFT.value
    await db.commit()

    # 验证双行均落库（驳回也要保留审计轨迹）
    approvals = (
        await db.execute(
            select(ConfigApproval).where(
                ConfigApproval.version_id == version.version_id
            )
        )
    ).scalars().all()
    assert len(approvals) == 2
    assert any(a.decision == "REJECTED" for a in approvals)
