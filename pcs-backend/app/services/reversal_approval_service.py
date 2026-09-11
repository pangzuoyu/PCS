"""ReversalApprovalService — 反向签署 (REVERSAL_APPROVAL) 闭环（ADR-0010 + ADR-0002）。

撤销路径分支（spec V1.0 §3.4）：
- CHANGE_PENDING 阶段：设计人自行放弃（ABANDON_CHANGE → CHECKED）
- CHANGED 阶段：经 REVERSAL_PENDING 由撤销批准链批准
  - 3 级矩阵取 REVIEWER 角色；4 级取 APPROVER 角色
- 已凭生效的变更（locked_by_deliverable=True）：只能发起反向新变更
  （change_type=CHANGE_REVERSAL），不可 REVERSAL_APPROVAL

状态机三事件（在 state_machine.py 锁定）：
- CHANGED → REVERSAL_PENDING（REQUEST_REVERSAL）
- REVERSAL_PENDING → CHECKED（APPROVE_REVERSAL + 恢复快照）
- REVERSAL_PENDING → CHANGED（REJECT_REVERSAL）

本服务封装状态机三事件 + 业务校验（locked_by_deliverable / reason 必填 /
非 CHANGED 不能发起），并触发 ACTIVE 快照数据恢复 + CONSUMED 标记
（spec V1.0 §3.4 「撤销或放弃时回滚」）。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import RecordChangeSnapshot
from app.models.enums import AuditAction, RecordSignStatus9, SnapshotStatus
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError


class ReversalApprovalService:
    """反向签署服务（SIM-40 闭环）。

    公开 API：
    - request_reversal：CHANGED → REVERSAL_PENDING
    - approve_reversal：REVERSAL_PENDING → CHECKED + 快照恢复
    - reject_reversal：REVERSAL_PENDING → CHANGED
    """

    # 合法起点状态（与 state_machine ALLOWED_TRANSITIONS 对齐）
    _REQUEST_FROM = RecordSignStatus9.CHANGED.value
    _APPROVE_FROM = RecordSignStatus9.REVERSAL_PENDING.value
    _REJECT_FROM = RecordSignStatus9.REVERSAL_PENDING.value

    @classmethod
    async def _load_record(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
        record_table: type,
    ) -> Any:
        """加载业务记录；不存在 → 404。"""
        rec = await db.get(record_table, record_id)
        if rec is None:
            raise PcsError(
                f"记录 {record_id} 不存在",
                code="RECORD_NOT_FOUND",
                status=404,
            )
        return rec

    @classmethod
    async def _load_active_snapshot(
        cls,
        db: AsyncSession,
        record: Any,
    ) -> RecordChangeSnapshot | None:
        """查询 record 对应的最新 ACTIVE 快照（用于 approve 时恢复数据）。"""
        record_id = getattr(record, "record_id", None)
        record_type = type(record).__name__
        snap = (
            await db.execute(
                select(RecordChangeSnapshot)
                .where(
                    RecordChangeSnapshot.record_type == record_type,
                    RecordChangeSnapshot.record_id == record_id,
                    RecordChangeSnapshot.snapshot_status == SnapshotStatus.ACTIVE.value,
                )
                .order_by(RecordChangeSnapshot.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return snap

    @classmethod
    async def _restore_snapshot(
        cls,
        db: AsyncSession,
        record: Any,
    ) -> bool:
        """恢复 ACTIVE 快照到 record 字段 + 标记 CONSUMED。返回是否找到快照。"""
        snap = await cls._load_active_snapshot(db, record)
        if snap is None:
            return False
        data = snap.data_snapshot_json or {}
        for col, val in data.items():
            if hasattr(record, col):
                setattr(record, col, val)
        snap.snapshot_status = SnapshotStatus.CONSUMED.value
        return True

    @classmethod
    async def request_reversal(
        cls,
        db: AsyncSession,
        *,
        record_id: uuid.UUID,
        actor: Any,
        reason: str,
        record_table: type,
    ) -> dict[str, Any]:
        """发起撤销申请：CHANGED → REVERSAL_PENDING。

        ADRS：
        - ADR-0002：撤销仅对 CHANGED 状态发起
        - ADR-0010：REVERSAL_PENDING 由撤销批准链批准（角色校验交给签名矩阵层）
        - spec V1.0 §3.4：已对外生效（locked_by_deliverable=True）只能走 CHANGE_REVERSAL

        Args:
            db: 异步 Session
            record_id: 业务记录 PK（必须 sign_status=CHANGED 且未锁定）
            actor: 申请人（DESIGNER / CHECKER / APPROVER）
            reason: 撤销理由（必填）
            record_table: 业务记录 ORM 模型类

        Returns:
            dict 形如 {"record_id": ..., "from": "CHANGED", "to": "REVERSAL_PENDING"}

        Raises:
            PcsError 404 if record_id 不存在
            PcsError 409 if 状态非 CHANGED 或已锁定
            PcsError 422 if reason 为空
        """
        if not reason or not reason.strip():
            raise PcsError(
                "撤销申请必须填写理由",
                code="REVERSAL_REASON_REQUIRED",
                status=422,
            )

        rec = await cls._load_record(db, record_id, record_table)

        # 起点校验：仅 CHANGED 可发起
        if rec.sign_status != cls._REQUEST_FROM:
            raise PcsError(
                f"记录 {record_id} 当前 {rec.sign_status} 不能发起撤销"
                f"（仅 CHANGED 可发起）",
                code="REVERSAL_BAD_STATE",
                status=409,
            )

        # 已锁定：必须走 CHANGE_REVERSAL 新变更单
        if getattr(rec, "locked_by_deliverable", False):
            raise PcsError(
                f"记录 {record_id} 已被交付物绑定（已对外生效），"
                f"不能走撤销流程，需发起 change_type=CHANGE_REVERSAL 反向新变更"
                f"（spec V1.0 §3.4）",
                code="REVERSAL_LOCKED_USE_CHANGE_REVERSAL",
                status=409,
            )

        old_status = rec.sign_status
        now = datetime.now(UTC)
        rec.sign_status = RecordSignStatus9.REVERSAL_PENDING.value
        rec.reversal_requested_at = now
        rec.reversal_requested_by = getattr(actor, "user_id", None)
        rec.reversal_reason = reason

        await AuditService(db).write(
            action=AuditAction.CHANGE_REVERSAL_REQUESTED,
            resource_type=type(rec).__name__,
            resource_id=str(record_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": RecordSignStatus9.REVERSAL_PENDING.value,
                "reason": reason,
            },
        )
        await db.commit()

        return {
            "record_id": str(record_id),
            "from": old_status,
            "to": RecordSignStatus9.REVERSAL_PENDING.value,
            "reason": reason,
            "snapshot_restored": False,
        }

    @classmethod
    async def approve_reversal(
        cls,
        db: AsyncSession,
        *,
        record_id: uuid.UUID,
        actor: Any,
        record_table: type,
    ) -> dict[str, Any]:
        """批准撤销：REVERSAL_PENDING → CHECKED + 恢复 ACTIVE 快照。

        ADRS：
        - ADR-0010：3 级取 REVIEWER / 4 级取 APPROVER（角色校验由签名矩阵层做）
        - spec V1.0 §3.4 「撤销或放弃时回滚」

        Args:
            db: 异步 Session
            record_id: 业务记录 PK（必须 sign_status=REVERSAL_PENDING）
            actor: 审批人（角色校验交给矩阵层）
            record_table: 业务记录 ORM 模型类

        Returns:
            dict 形如 {"record_id": ..., "from": "REVERSAL_PENDING",
                       "to": "CHECKED", "snapshot_restored": bool}

        Raises:
            PcsError 404 if record_id 不存在
            PcsError 409 if 状态非 REVERSAL_PENDING
        """
        rec = await cls._load_record(db, record_id, record_table)

        if rec.sign_status != cls._APPROVE_FROM:
            raise PcsError(
                f"记录 {record_id} 当前 {rec.sign_status} 不能批准撤销"
                f"（仅 REVERSAL_PENDING 可批准）",
                code="REVERSAL_BAD_STATE",
                status=409,
            )

        old_status = rec.sign_status
        rec.sign_status = RecordSignStatus9.CHECKED.value

        # 恢复 ACTIVE 快照（spec V1.0 §3.4 撤销或放弃时回滚）
        snapshot_restored = await cls._restore_snapshot(db, rec)

        await AuditService(db).write(
            action=AuditAction.CHANGE_REVERSAL_APPROVED,
            resource_type=type(rec).__name__,
            resource_id=str(record_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": RecordSignStatus9.CHECKED.value,
                "snapshot_restored": snapshot_restored,
            },
        )
        await db.commit()

        result = {
            "record_id": str(record_id),
            "from": old_status,
            "to": RecordSignStatus9.CHECKED.value,
            "snapshot_restored": snapshot_restored,
        }
        return result

    @classmethod
    async def reject_reversal(
        cls,
        db: AsyncSession,
        *,
        record_id: uuid.UUID,
        actor: Any,
        reason: str,
        record_table: type,
    ) -> dict[str, Any]:
        """拒绝撤销：REVERSAL_PENDING → CHANGED（维持 CHANGED 等待关闭凭证）。

        Args:
            db: 异步 Session
            record_id: 业务记录 PK（必须 sign_status=REVERSAL_PENDING）
            actor: 审批人
            reason: 拒绝理由（必填）
            record_table: 业务记录 ORM 模型类

        Returns:
            dict 形如 {"record_id": ..., "from": "REVERSAL_PENDING", "to": "CHANGED"}

        Raises:
            PcsError 404 if record_id 不存在
            PcsError 409 if 状态非 REVERSAL_PENDING
            PcsError 422 if reason 为空
        """
        if not reason or not reason.strip():
            raise PcsError(
                "拒绝撤销必须填写理由",
                code="REVERSAL_REJECTION_REASON_REQUIRED",
                status=422,
            )

        rec = await cls._load_record(db, record_id, record_table)

        if rec.sign_status != cls._REJECT_FROM:
            raise PcsError(
                f"记录 {record_id} 当前 {rec.sign_status} 不能拒绝撤销"
                f"（仅 REVERSAL_PENDING 可拒绝）",
                code="REVERSAL_BAD_STATE",
                status=409,
            )

        old_status = rec.sign_status
        now = datetime.now(UTC)
        rec.sign_status = RecordSignStatus9.CHANGED.value
        rec.reversal_rejected_at = now
        rec.reversal_rejected_by = getattr(actor, "user_id", None)
        rec.reversal_rejected_reason = reason

        await AuditService(db).write(
            action=AuditAction.CHANGE_REVERSAL_REJECTED,
            resource_type=type(rec).__name__,
            resource_id=str(record_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": RecordSignStatus9.CHANGED.value,
                "reason": reason,
            },
        )
        await db.commit()

        return {
            "record_id": str(record_id),
            "from": old_status,
            "to": RecordSignStatus9.CHANGED.value,
            "reason": reason,
        }


__all__ = ["ReversalApprovalService"]
