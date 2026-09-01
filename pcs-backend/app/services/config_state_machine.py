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

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ConfigAsset, ConfigVersion
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


# transition → next status（如果需要"中间不变"的 OBSOLETE / 拒绝等也唯一确定）
_NEXT_STATUS: dict[ConfigTransition, str] = {
    ConfigTransition.SUBMIT: ConfigStatus.PENDING.value,
    ConfigTransition.APPROVE: ConfigStatus.APPROVED.value,
    ConfigTransition.REJECT: ConfigStatus.DRAFT.value,
    ConfigTransition.PUBLISH: ConfigStatus.PUBLISHED.value,
    ConfigTransition.OBSOLETE: ConfigStatus.OBSOLETE.value,
}
