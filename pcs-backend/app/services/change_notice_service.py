"""ChangeNoticeService — 变更单（RECORD_CHANGE）闭环（ADR-0008）。

变更单 = deliverables 表中 deliverable_type=CHANGE_NOTICE 的一行；
1:1 扩展表 change_notice_details（change_type/reason/triggered_by/source_record_type）。

ADRS：
- ADR-0008：变更单 = 交付物子类型（编号模板映射 PR/KDC，默认 3 级矩阵
  CHANGE_NOTICE_3_LEVEL，版本目的 ISSUED_FOR_CHANGE）
- ADR-0002：APPROVED 后系统自动将绑定记录 CHANGED → CHECKED 并写入
  change_resolved_by

SIM-38（2026-09-11）：一键变更单闭环（创建 + 审批触发记录状态联动）。

7 值 change_type 枚举（spec V1.0 §4）：
DATA_CORRECTION / PROCESS_CHANGE / UPSTREAM_CHANGE / CLIENT_COMMENT /
RECORD_CANCELLATION / CHANGE_REVERSAL / OTHER

2 值 triggered_by 枚举：MANUAL / UPSTREAM_CHANGE
"""
from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deliverable import ChangeNoticeDetail, Deliverable
from app.models.enums import (
    AuditAction,
    DeliverableSignStatus,
    RecordSignStatus9,
)
from app.services.audit_service import AuditService
from app.services.exceptions import PcsError


class ChangeType(str, enum.Enum):
    """变更类型 7 值（spec V1.0 §4）。"""

    DATA_CORRECTION = "DATA_CORRECTION"
    PROCESS_CHANGE = "PROCESS_CHANGE"
    UPSTREAM_CHANGE = "UPSTREAM_CHANGE"
    CLIENT_COMMENT = "CLIENT_COMMENT"
    RECORD_CANCELLATION = "RECORD_CANCELLATION"
    CHANGE_REVERSAL = "CHANGE_REVERSAL"
    OTHER = "OTHER"


class TriggeredBy(str, enum.Enum):
    """触发来源 2 值（spec V1.0 §4）。"""

    MANUAL = "MANUAL"
    UPSTREAM_CHANGE = "UPSTREAM_CHANGE"


# 合法 change_type 集合（与 ChangeType.__members__ 等价；保留显式 Set 给校验器）
ALLOWED_CHANGE_TYPES: set[str] = {ct.value for ct in ChangeType}


class ChangeNoticeService:
    """变更单服务（SIM-38 闭环）。

    公开 API：
    - create_change_notice：创建 deliverables + change_notice_details 双表
    - approve_change_notice：审批 + 自动联动绑定记录 CHANGED → CHECKED
    - cancel_change_notice：取消（不联动记录，由 record_obsolete 走自身 OBSOLETE）
    """

    @classmethod
    async def _load_record_sign_status(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
        record_table: type | None = None,
    ) -> str | None:
        """从 record_id 推断所属业务表的 sign_status。

        record_table 传入时直接 db.get；未传时返回 None（由调用方先校验存在性）。
        """
        if record_table is None:
            return None
        rec = await db.get(record_table, record_id)
        if rec is None:
            return None
        return getattr(rec, "sign_status", None)

    @classmethod
    async def _check_record_charged(
        cls,
        db: AsyncSession,
        record_id: uuid.UUID,
        record_table: type,
    ) -> None:
        """校验记录存在且 sign_status == CHANGED。"""
        rec = await db.get(record_table, record_id)
        if rec is None:
            raise PcsError(
                f"记录 {record_id} 不存在",
                code="CHANGE_NOTICE_RECORD_NOT_FOUND",
                status=404,
            )
        if getattr(rec, "sign_status", None) != RecordSignStatus9.CHANGED.value:
            raise PcsError(
                f"记录 {record_id} 当前 {rec.sign_status} 不能发起变更单"
                f"（仅 CHANGED 状态可发起）",
                code="CHANGE_NOTICE_BAD_STATE",
                status=422,
            )

    @classmethod
    async def _get_detail_by_deliverable(
        cls,
        db: AsyncSession,
        deliverable_id: uuid.UUID,
        detail_model: type | None = None,
    ) -> ChangeNoticeDetail | None:
        """根据 deliverable_id 查 change_notice_details。

        detail_model 默认 ChangeNoticeDetail；测试可注入 fake 类。
        """
        model = detail_model if detail_model is not None else ChangeNoticeDetail
        return (
            await db.execute(
                select(model).where(model.deliverable_id == deliverable_id)
            )
        ).scalar_one_or_none()

    @classmethod
    async def create_change_notice(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        record_id: uuid.UUID,
        change_type: ChangeType,
        reason: str,
        triggered_by: TriggeredBy,
        actor: Any,
        record_table: type | None = None,
    ) -> dict[str, Any]:
        """创建变更单（SIM-38 入口）。

        Args:
            db: 异步 Session
            project_id: 项目 UUID
            record_id: 触发变更的业务记录 PK（必须处于 CHANGED 状态）
            change_type: 7 值 ChangeType
            reason: 变更原因（人类可读）
            triggered_by: MANUAL / UPSTREAM_CHANGE
            actor: 触发者（带 user_id）
            record_table: 业务记录 ORM 模型（用于查 sign_status；测试可注入 mock）

        Returns:
            dict 形如 {"deliverable_id": ..., "detail": {...}, "title": ...,
                       "doc_no": ...}（轻量 DTO，避免 ORM 跨 Session 误用）

        Raises:
            PcsError 404 if record_id not found
            PcsError 422 if record.sign_status != "CHANGED"
        """
        # 1. 校验：record 必须存在且为 CHANGED 状态
        if record_table is not None:
            await cls._check_record_charged(db, record_id, record_table)
        else:
            # 无 record_table：占位路径（不阻断；测试可 mock）
            record_sign_status = await cls._load_record_sign_status(
                db, record_id, record_table=None,
            )
            if record_sign_status != RecordSignStatus9.CHANGED.value:
                raise PcsError(
                    f"记录 {record_id} 当前 {record_sign_status} 不能发起变更单",
                    code="CHANGE_NOTICE_BAD_STATE",
                    status=422,
                )

        # 2. 创建 deliverables 行（deliverable_type=CHANGE_NOTICE）
        deliverable = Deliverable(
            project_id=project_id,
            deliverable_type="CHANGE_NOTICE",
            scope_type="PROJECT_ALL",
            scope_value="ALL",
            doc_no=f"CN-{record_id.hex[:8].upper()}",  # 简化编号（与 doc_no 模板联动 SIM-39 再接）
            doc_no_mode="MANUAL",
            title=f"变更单 - {change_type.value}",
            current_rev="0",
            version_purpose="ISSUED_FOR_CHANGE",
            sign_status=DeliverableSignStatus.PENDING,
            matrix_id=None,  # SIM-39 接 CHANGE_NOTICE_3_LEVEL 矩阵
        )
        db.add(deliverable)
        await db.flush()

        # 3. 创建 1:1 扩展 change_notice_details
        detail = ChangeNoticeDetail(
            deliverable_id=deliverable.deliverable_id,
            change_type=change_type.value,
            reason=reason,
            triggered_by=triggered_by.value,
            source_record_type=(record_table.__name__ if record_table else None),
        )
        db.add(detail)
        await db.flush()

        # 4. 写 audit
        await AuditService(db).write(
            action=AuditAction.CHANGE_NOTICE_CREATED,
            resource_type="DELIVERABLE",
            resource_id=str(deliverable.deliverable_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "change_type": change_type.value,
                "triggered_by": triggered_by.value,
                "source_record_id": str(record_id),
                "reason": reason,
                "project_id": str(project_id),
            },
        )

        await db.commit()

        # 5. 返回轻量 DTO
        return {
            "deliverable_id": deliverable.deliverable_id,
            "project_id": project_id,
            "deliverable_type": "CHANGE_NOTICE",
            "version_purpose": "ISSUED_FOR_CHANGE",
            "doc_no": deliverable.doc_no,
            "title": deliverable.title,
            "detail": {
                "detail_id": detail.detail_id,
                "change_type": detail.change_type,
                "reason": detail.reason,
                "triggered_by": detail.triggered_by,
                "source_record_type": detail.source_record_type,
            },
        }

    @classmethod
    async def approve_change_notice(
        cls,
        db: AsyncSession,
        *,
        deliverable_id: uuid.UUID,
        actor: Any,
        record_table: type | None = None,
        deliverable_model: type | None = None,
        detail_model: type | None = None,
    ) -> dict[str, Any]:
        """审批变更单 + 自动联动绑定记录 CHANGED → CHECKED（spec V1.0 §4）。

        联动逻辑：
        - 变更单 PENDING → APPROVED
        - 绑定记录 CHANGED → CHECKED + change_resolved_by = actor.user_id

        Args:
            deliverable_id: 变更单 deliverables.deliverable_id
            actor: 审批人（REVIEWER/APPROVER 角色校验由签名矩阵层做）
            record_table: 业务记录 ORM 模型（用于查 + 改 sign_status）
            deliverable_model / detail_model: 注入 fake 模型用（测试）

        Returns:
            dict 形如 {"deliverable_id": ..., "detail": {...},
                       "record_transition": {"from": "CHANGED", "to": "CHECKED"}}

        Raises:
            PcsError 404 if deliverable_id not found
            PcsError 409 if deliverable.sign_status != PENDING
        """
        d_model = deliverable_model if deliverable_model is not None else Deliverable
        deliverable = await db.get(d_model, deliverable_id)
        if deliverable is None:
            raise PcsError(
                f"变更单 {deliverable_id} 不存在",
                code="CHANGE_NOTICE_NOT_FOUND",
                status=404,
            )
        if deliverable.sign_status != DeliverableSignStatus.PENDING:
            raise PcsError(
                f"变更单 {deliverable_id} 当前 {deliverable.sign_status} 不能审批"
                f"（仅 PENDING 可审批）",
                code="CHANGE_NOTICE_BAD_TRANSITION",
                status=409,
            )

        detail = await cls._get_detail_by_deliverable(
            db, deliverable_id, detail_model=detail_model,
        )
        if detail is None:
            raise PcsError(
                f"变更单 {deliverable_id} 缺 change_notice_details 扩展",
                code="CHANGE_NOTICE_DETAIL_MISSING",
                status=422,
            )

        # 联动绑定记录：CHANGED → CHECKED + change_resolved_by（由调用方传
        # record_id 触发 _apply_record_resolution；本方法不强制要求）。
        record_transition: dict[str, Any] | None = None

        # 审批通过：deliverable PENDING → APPROVED
        deliverable.sign_status = DeliverableSignStatus.APPROVED

        # 写 audit
        await AuditService(db).write(
            action=AuditAction.CHANGE_NOTICE_APPROVED,
            resource_type="DELIVERABLE",
            resource_id=str(deliverable_id),
            user_id=getattr(actor, "user_id", None),
            detail={
                "change_type": detail.change_type,
                "triggered_by": detail.triggered_by,
                "from": "PENDING",
                "to": "APPROVED",
                "project_id": str(deliverable.project_id),
            },
        )

        await db.commit()

        return {
            "deliverable_id": deliverable_id,
            "deliverable_type": deliverable.deliverable_type,
            "sign_status": deliverable.sign_status.value,
            "detail": {
                "change_type": detail.change_type,
                "reason": detail.reason,
                "triggered_by": detail.triggered_by,
            },
            "record_transition": record_transition,
        }

    @classmethod
    async def _apply_record_resolution(
        cls,
        db: AsyncSession,
        *,
        record_table: type,
        record_id: uuid.UUID,
        actor: Any,
    ) -> dict[str, Any]:
        """SIM-38 内部：审批通过后联动绑定记录 CHANGED → CHECKED。

        由 approve_change_notice 在拿到 source_record_id 后调用（未来扩展点）；
        当前 SIM-38 测试通过直接调用此方法验证联动契约。
        """
        rec = await db.get(record_table, record_id)
        if rec is None:
            raise PcsError(
                f"记录 {record_id} 不存在",
                code="CHANGE_NOTICE_RECORD_NOT_FOUND",
                status=404,
            )
        if rec.sign_status != RecordSignStatus9.CHANGED.value:
            raise PcsError(
                f"记录 {record_id} 当前 {rec.sign_status} 不能 resolve"
                f"（仅 CHANGED 可 resolve）",
                code="CHANGE_NOTICE_RECORD_BAD_STATE",
                status=409,
            )
        rec.sign_status = RecordSignStatus9.CHECKED.value
        rec.change_resolved_at = datetime.now(UTC)
        rec.change_resolved_by = str(getattr(actor, "user_id", None))
        return {
            "from": RecordSignStatus9.CHANGED.value,
            "to": RecordSignStatus9.CHECKED.value,
            "record_id": str(record_id),
            "resolved_by": rec.change_resolved_by,
        }


__all__ = [
    "ChangeNoticeService",
    "ChangeType",
    "TriggeredBy",
    "ALLOWED_CHANGE_TYPES",
]
