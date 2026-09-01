"""ConfigStateMachine — 配置资产（P2 Sprint 1.2 / SUP-001 §2.1）。

5 态骨架：DRAFT → PENDING → APPROVED → PUBLISHED → OBSOLETE；
DRAFT、APPROVED 可经 OBSOLETE 直接出局。

调用方式（与 P1 StateMachineService 一致）：
- 守卫 → 改 asset.status → 写 audit 落库 → caller session.commit()。

Schema 真实结构（Task 1.2 不做 schema 变更）：
- `ConfigAsset.current_version` 是 String(50) 列，不是 ConfigVersion 关系；
  `version` 参数保留供元数据/将来审计校验使用，本版本不读取其属性。
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigApproval, ConfigAsset, ConfigVersion
from app.models.enums import AuditAction, ConfigStatus, ConfigTransition
from app.services.audit_service import AuditService


class InvalidTransitionError(Exception):
    """ConfigStateMachine 非法转移。"""


class _ActorLike(Protocol):
    """最小 actor 协议 — Task 1.2 仅需 user_id（项目内目前无 AuthUser 类）。"""

    user_id: UUID


# transition → audit action
TRANSITION_AUDIT_ACTION: dict[ConfigTransition, AuditAction] = {
    ConfigTransition.SUBMIT: AuditAction.CONFIG_ASSET_SUBMITTED,
    ConfigTransition.APPROVE: AuditAction.CONFIG_ASSET_APPROVED,
    ConfigTransition.REJECT: AuditAction.CONFIG_ASSET_REJECTED,
    ConfigTransition.PUBLISH: AuditAction.CONFIG_ASSET_PUBLISHED,
    ConfigTransition.OBSOLETE: AuditAction.CONFIG_ASSET_OBSOLETED,
}


class ConfigStateMachine:
    """配置资产状态机。"""

    TRANSITIONS: dict[str, set[ConfigTransition]] = {
        ConfigStatus.DRAFT.value: {
            ConfigTransition.SUBMIT,
            ConfigTransition.OBSOLETE,
        },
        ConfigStatus.PENDING.value: {
            ConfigTransition.APPROVE,
            ConfigTransition.REJECT,
        },
        ConfigStatus.APPROVED.value: {
            ConfigTransition.PUBLISH,
            ConfigTransition.OBSOLETE,
        },
        ConfigStatus.PUBLISHED.value: {ConfigTransition.OBSOLETE},
        ConfigStatus.OBSOLETE.value: set(),
    }

    # 双段签（CATEGORY_2）：两段签均 APPROVED → APPROVED，任一 REJECTED → DRAFT
    DOUBLE_SIGNOFF_CATEGORIES: set[str] = {"CATEGORY_2"}

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def transition(
        self,
        asset: ConfigAsset,
        version: ConfigVersion,
        *,
        action: ConfigTransition,
        actor: _ActorLike,
        role: str | None = None,
        reason: str | None = None,
    ) -> ConfigVersion:
        """执行状态转移 + 审计落库。caller 负责 session.commit()。

        Args:
            asset: 目标 ConfigAsset。
            version: 当前 ConfigVersion（元数据/将来使用；本版本不读取其属性）。
            action: ConfigTransition 事件。
            actor: 触发者（duck-typed；需有 .user_id: UUID 字段）。
            role: 可选审批角色，存入审计 detail。
            reason: 可选原因/备注，存入审计 detail。
        """
        allowed = self.TRANSITIONS.get(asset.status, set())
        if action not in allowed:
            raise InvalidTransitionError(
                f"{asset.status} → {action.value} 不允许"
            )
        old_status = asset.status
        asset.status = _NEXT_STATUS[action]
        await self.session.flush()

        detail: dict[str, Any] = {
            "from": old_status,
            "to": asset.status,
            "transition": action.value,
            "version_id": str(version.version_id) if version is not None else None,
        }
        if role is not None:
            detail["role"] = role
        if reason is not None:
            detail["reason"] = reason

        await self.audit.write(
            action=TRANSITION_AUDIT_ACTION[action],
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            user_id=actor.user_id,
            detail=detail,
        )
        return version

    async def record_approval(
        self,
        asset: ConfigAsset,
        version: ConfigVersion,
        *,
        approver_id: UUID,
        role: str,
        decision: str,  # "APPROVED" | "REJECTED"
        actor: _ActorLike,
        reason: str | None = None,
    ) -> ConfigApproval:
        """插入 config_approvals 行 + 状态判定 + 审计落库。

        双段签（CATEGORY_2）：两段签均 APPROVED → APPROVED；任一 REJECTED → DRAFT。
        单层（CATEGORY_3 等）：单行 APPROVED → APPROVED；REJECTED → DRAFT。
        caller 负责 session.commit()。
        """
        approval = ConfigApproval(
            version_id=version.version_id,
            approver_id=approver_id,
            approver_role=role,
            decision=decision,
        )
        self.session.add(approval)
        await self.session.flush()  # 让 approval 立即可查，避免脏读

        # 重新查询该 version 下所有 approvals（确保包含本行）
        approvals = (
            await self.session.execute(
                select(ConfigApproval).where(
                    ConfigApproval.version_id == version.version_id
                )
            )
        ).scalars().all()

        old_status = asset.status
        if asset.category in self.DOUBLE_SIGNOFF_CATEGORIES:
            # 双段签：任一驳回即回 DRAFT；全部批准才进 APPROVED
            if any(a.decision == "REJECTED" for a in approvals):
                asset.status = ConfigStatus.DRAFT.value
            elif (
                len(approvals) >= 2
                and all(a.decision == "APPROVED" for a in approvals)
            ):
                asset.status = ConfigStatus.APPROVED.value
            # 否则保持 PENDING（等下一段签）
        else:
            # 单层：单行决定
            if decision == "REJECTED":
                asset.status = ConfigStatus.DRAFT.value
            elif decision == "APPROVED":
                asset.status = ConfigStatus.APPROVED.value

        await self.session.flush()

        # 审计落库（D20 一致 — AuditService.write 真实签名）
        audit_action = (
            AuditAction.CONFIG_ASSET_REJECTED
            if decision == "REJECTED"
            else AuditAction.CONFIG_ASSET_APPROVED
        )
        detail: dict[str, Any] = {
            "from": old_status,
            "to": asset.status,
            "approver_role": role,
            "approver_id": str(approver_id),
            "approval_id": str(approval.approval_id),
            "category": asset.category,
            "signoff_mode": (
                "DOUBLE" if asset.category in self.DOUBLE_SIGNOFF_CATEGORIES
                else "SINGLE"
            ),
        }
        if reason is not None:
            detail["reason"] = reason

        await self.audit.write(
            action=audit_action,
            resource_type="CONFIG",
            resource_id=str(asset.asset_id),
            user_id=actor.user_id,
            detail=detail,
        )
        return approval


# transition → next status（如果需要"中间不变"的 OBSOLETE / 拒绝等也唯一确定）
_NEXT_STATUS: dict[ConfigTransition, str] = {
    ConfigTransition.SUBMIT: ConfigStatus.PENDING.value,
    ConfigTransition.APPROVE: ConfigStatus.APPROVED.value,
    ConfigTransition.REJECT: ConfigStatus.DRAFT.value,
    ConfigTransition.PUBLISH: ConfigStatus.PUBLISHED.value,
    ConfigTransition.OBSOLETE: ConfigStatus.OBSOLETE.value,
}
