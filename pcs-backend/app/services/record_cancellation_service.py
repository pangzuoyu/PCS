"""RecordCancellationService — 记录弃用 (RECORD_CANCELLATION) 闭环（ADR-0009 + ADR-0002）。

弃用路径分支（spec V1.0 §3.4）：
1. **未绑定记录**（locked_by_deliverable=False）：直接 OBSOLETE，无凭证；
2. **已绑定记录**（locked_by_deliverable=True）：必须先创建 change_type=RECORD_CANCELLATION
   变更单；变更单 APPROVED 后由本服务 `bound_obsolete_via_deliverable` 联动 OBSOLETE。

位号终身唯一（ADR-0009）：(project_id, tag_number/line_no) UNIQUE 约束覆盖含 OBSOLETE
全部记录，OBSOLETE 不清空 tag_number，弃用后永不复用；替代分配新号。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction, RecordSignStatus9
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError


class BoundObsoleteError(PcsError):
    """已绑定记录拒绝直接 OBSOLETE 异常。"""

    code = "RECORD_BOUND_USE_CHANGE_NOTICE"
    status = 409

    def __init__(self, message: str, **kw: Any) -> None:
        super().__init__(message, **kw)


class RecordCancellationService:
    """记录弃用服务（SIM-39 闭环）。

    公开 API：
    - obsolete：直接弃用入口（仅未绑定记录）
    - bound_obsolete_via_deliverable：变更单 APPROVED 后联动弃用入口（已绑定记录）
    """

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
    async def _validate_obsolete_eligible(
        cls,
        rec: Any,
        *,
        allow_obsolete: bool = True,
    ) -> None:
        """校验记录可 OBSOLETE：sign_status != OBSOLETE 且按需 locked_by_deliverable 校验。"""
        current = getattr(rec, "sign_status", None)
        if current == RecordSignStatus9.OBSOLETE.value:
            raise PcsError(
                f"记录 {getattr(rec, 'record_id', '?')} 已 OBSOLETE，不能再次弃用",
                code="RECORD_ALREADY_OBSOLETE",
                status=409,
            )
        if not allow_obsolete:
            raise PcsError(
                f"记录 {getattr(rec, 'record_id', '?')} 未绑定，应走直接 OBSOLETE 路径",
                code="RECORD_NOT_BOUND",
                status=422,
            )

    @classmethod
    async def _apply_obsolete(
        cls,
        db: AsyncSession,
        *,
        rec: Any,
        actor: Any,
        reason: str,
        obsoleted_via: str,
        deliverable_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """应用 OBSOLETE：写 sign_status + obsoleted_* + audit + commit。"""
        old_status = getattr(rec, "sign_status", None)
        now = datetime.now(UTC)
        rec.sign_status = RecordSignStatus9.OBSOLETE.value
        rec.obsoleted_at = now
        rec.obsoleted_by = getattr(actor, "user_id", None)
        rec.obsoleted_reason = reason
        if deliverable_id is not None:
            rec.obsoleted_via_deliverable_id = deliverable_id

        await AuditService(db).write(
            action=AuditAction.RECORD_OBSOLETED,
            resource_type=type(rec).__name__,
            resource_id=str(getattr(rec, "record_id", "")),
            user_id=getattr(actor, "user_id", None),
            detail={
                "from": old_status,
                "to": RecordSignStatus9.OBSOLETE.value,
                "reason": reason,
                "obsoleted_via": obsoleted_via,
                "deliverable_id": str(deliverable_id) if deliverable_id else None,
            },
        )
        await db.commit()
        return {
            "record_id": str(getattr(rec, "record_id", "")),
            "from": old_status,
            "to": RecordSignStatus9.OBSOLETE.value,
            "obsoleted_via": obsoleted_via,
            "deliverable_id": str(deliverable_id) if deliverable_id else None,
        }

    @classmethod
    async def obsolete(
        cls,
        db: AsyncSession,
        *,
        record_id: uuid.UUID,
        actor: Any,
        reason: str,
        record_table: type,
    ) -> dict[str, Any]:
        """直接弃用入口（未绑定记录专用）。

        ADRS：
        - ADR-0009：未绑定免凭证 OBSOLETE
        - 已绑定 → BoundObsoleteError，提示需 RECORD_CANCELLATION 变更单

        Args:
            db: 异步 Session
            record_id: 业务记录 PK
            actor: 触发者
            reason: 弃用原因
            record_table: 业务记录 ORM 模型类

        Returns:
            dict 形如 {"record_id": ..., "from": ..., "to": "OBSOLETE",
                       "obsoleted_via": "DIRECT"}

        Raises:
            PcsError 404 if record_id 不存在
            PcsError 409 if 记录已 OBSOLETE
            BoundObsoleteError 409 if 记录已被交付物绑定
        """
        rec = await cls._load_record(db, record_id, record_table)

        # 已 OBSOLETE 直接拒绝
        if getattr(rec, "sign_status", None) == RecordSignStatus9.OBSOLETE.value:
            raise PcsError(
                f"记录 {record_id} 已 OBSOLETE，不能再次弃用",
                code="RECORD_ALREADY_OBSOLETE",
                status=409,
            )

        # 已绑定 → 走变更单
        if getattr(rec, "locked_by_deliverable", False):
            raise BoundObsoleteError(
                f"记录 {record_id} 已被交付物绑定，必须先创建 "
                f"change_type=RECORD_CANCELLATION 的变更单并经审批通过"
                f"（spec V1.0 §3.4 / ADR-0009）",
            )

        return await cls._apply_obsolete(
            db,
            rec=rec,
            actor=actor,
            reason=reason,
            obsoleted_via="DIRECT",
        )

    @classmethod
    async def bound_obsolete_via_deliverable(
        cls,
        db: AsyncSession,
        *,
        record_id: uuid.UUID,
        deliverable_id: uuid.UUID,
        actor: Any,
        record_table: type,
    ) -> dict[str, Any]:
        """已绑定记录联动 OBSOLETE（ChangeNoticeService.approve 阶段调用）。

        调用时机：change_type=RECORD_CANCELLATION 变更单 APPROVED 后。
        写入 obsoleted_via_deliverable_id 字段供审计追溯。

        Args:
            db: 异步 Session
            record_id: 业务记录 PK（必须 locked_by_deliverable=True）
            deliverable_id: 触发弃用的变更单 deliverables.deliverable_id
            actor: 审批人
            record_table: 业务记录 ORM 模型类

        Returns:
            dict 形如 {"record_id": ..., "obsoleted_via": "DELIVERABLE",
                       "deliverable_id": "..."}

        Raises:
            PcsError 404 if record_id 不存在
            PcsError 409 if 记录已 OBSOLETE
            PcsError 422 if 记录未绑定（应走直接 OBSOLETE）
        """
        rec = await cls._load_record(db, record_id, record_table)

        if getattr(rec, "sign_status", None) == RecordSignStatus9.OBSOLETE.value:
            raise PcsError(
                f"记录 {record_id} 已 OBSOLETE，不能再次弃用",
                code="RECORD_ALREADY_OBSOLETE",
                status=409,
            )

        if not getattr(rec, "locked_by_deliverable", False):
            raise PcsError(
                f"记录 {record_id} 未被交付物绑定，应走直接 OBSOLETE 路径",
                code="RECORD_NOT_BOUND",
                status=422,
            )

        return await cls._apply_obsolete(
            db,
            rec=rec,
            actor=actor,
            reason=f"经变更单 {deliverable_id} 弃用",
            obsoleted_via="DELIVERABLE",
            deliverable_id=deliverable_id,
        )


__all__ = ["RecordCancellationService", "BoundObsoleteError"]
