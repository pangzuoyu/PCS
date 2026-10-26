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

from app.models.deliverable import (
    ChangeNoticeDetail,
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
    RecordChangeSnapshot,
)
from app.models.enums import (
    AuditAction,
    DeliverableSignStatus,
    RecordSignStatus9,
    WorkflowProgressState,
    WorkflowType,
)
from app.services.audit_service import AuditService
from app.services.deliverable_service import DeliverableService
from app.services.exceptions import PcsError
from app.services.notifications.payload import NotificationPayload
from app.services.signature_matrix_service import SignatureMatrixService
from app.services.workflow_progress_writer import record_step


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
    - close_on_approved：签完最后一步 ⇒ 自动关掉绑定的记录（CHANGED → CHECKED）
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
    ) -> Any:
        """校验记录存在且 sign_status == CHANGED。**返回该行**。

        返回行而不只是校验：建单要把它写进 `deliverable_record_bindings`
        （记录哈希 = 新旧哈希对比的「新」那一半）⇒ 再查一次既多一次查询，
        又让「校验用的行」和「绑定的行」可能不是同一行。
        """
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
        return rec

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
        record_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """创建变更单（ADR-0008）。

        ## 三处「不得不」

        1. **签署矩阵**：变更单是交付物子类型，`Deliverable.matrix_id` 是
           NOT NULL + FK ⇒ 必须绑矩阵。矩阵从哪来由
           `SignatureMatrixService.ensure_change_notice_matrix` 惰性建行
           （`signature_matrices` 表原本恒 0 行且全仓无创建方 —— 没有它，
           变更单这条路根本走不通）。
        2. **scope 逐单唯一**：`uq_deliverables_scope` =
           (project_id, deliverable_type, scope_type, scope_value)
           ⇒ 用 PROJECT_ALL/ALL 的话，**同一项目的第二张变更单插不进去**。
           ⇒ 改用 CUSTOM + `CHANGE_NOTICE:{记录表名}:{记录ID}`。
        3. **观测写入点 2a**（ADR-0047 §①）：创建即写一行 CHANGE_NOTICE /
           PENDING —— 「流程已发起、尚未关闭」，不是 COMPLETED。

        Args:
            db: 异步 Session
            project_id: 项目 UUID
            record_id: 触发变更的业务记录 PK（必须处于 CHANGED 状态）
            change_type: 7 值 ChangeType
            reason: 变更原因（人类可读）
            triggered_by: MANUAL / UPSTREAM_CHANGE
            actor: 触发者（带 user_id）
            record_table: 业务记录 ORM 模型（用于查 sign_status）
            record_ids: **本次变更影响的全部记录**（TODO-078）—— 必须**包含**
                `record_id`（路径里的那条）；`None` / 空 ⇒ 只有 `record_id`
                （单记录 = 旧行为，**向后兼容**）。

        Returns:
            dict 形如 {"deliverable_id": ..., "workflow_id": ..., "matrix_id": ...,
                       "detail": {...}, "title": ..., "doc_no": ...}
            （轻量 DTO，避免 ORM 跨 Session 误用）

        Raises:
            PcsError 404 if record_id not found
            PcsError 422 if record.sign_status != "CHANGED"
            PcsError 409 if 该记录已有变更单
            PcsError 422 if `record_ids` 不含 `record_id` / 某条不属于本项目
        """
        # 1. 校验：record 必须存在且为 CHANGED 状态
        record: Any = None
        if record_table is not None:
            record = await cls._check_record_charged(db, record_id, record_table)
            record_type_name = record_table.__name__
            # ⚠️ **项目一致性自查**（TODO-084 第 2 条）：端点层今天传的是
            # `record.project_id`（对），但 service 是**对外入口** ⇒ 调用方
            # 传错项目 ⇒ 变更单建到别的项目名下，而 binding 指向一条**不属
            # 于该项目的记录** ⇒ 关闭凭证跨项目、审计链断。
            record_project_id = getattr(record, "project_id", None)
            if record_project_id is not None and record_project_id != project_id:
                raise PcsError(
                    f"记录 {record_id} 属于项目 {record_project_id}，"
                    f"不能建到项目 {project_id} 名下",
                    code="CHANGE_NOTICE_PROJECT_MISMATCH",
                    status=422,
                )
        else:
            # 无 record_table：**查不到记录状态** ⇒ 一律 422（不许建单）。
            # ⚠️ 旧注释写「不阻断」是错的：`_load_record_sign_status(None)` 恒返回
            # None ⇒ 下面必然抛 422。留着的意义只是「调用方忘了传 record_table
            # 时错误消息说的是状态不对而不是参数不对」。
            record_sign_status = await cls._load_record_sign_status(
                db, record_id, record_table=None,
            )
            if record_sign_status != RecordSignStatus9.CHANGED.value:
                raise PcsError(
                    f"记录 {record_id} 当前 {record_sign_status} 不能发起变更单",
                    code="CHANGE_NOTICE_BAD_STATE",
                    status=422,
                )
            record_type_name = ""

        # ⚠️ **变更单自己的 uuid**（编号与 scope 都由它派生 ⇒ 逐单唯一）。
        #    ⚠️ **不能**用记录 id 派生：一条记录**可以**有多张变更单
        #    （作废一张 ⇒ 另起一张）⇒ 记录派生的编号/scope 会撞唯一约束
        #    ⇒ 未捕获的 IntegrityError（500）。
        notice_id = uuid.uuid4()

        # 2. scope：逐单唯一（见 docstring 第 2 点）
        #    ⚠️ scope **以记录身份开头**（`CHANGE_NOTICE:{表名}:{记录ID}` ⇒ 与
        #    binding 的记录身份一致，由守卫测试钉住）**+ 逐单后缀**（本单的
        #    uuid 前 8 位 ⇒ 同一记录可以有多张单而不撞 `uq_deliverables_scope`）。
        scope_value = (
            f"CHANGE_NOTICE:{record_type_name}:{record_id}:{notice_id.hex[:8]}"
        )

        # 2b. ⚠️ **本次变更影响的记录集合**（TODO-078：一次变更常影响多条记录）
        #     - 必须**包含**主记录（路径里那条）⇒ 否则 422（口径明确）
        #     - 去重、保持顺序
        target_ids: list[uuid.UUID] = []
        for rid in [record_id, *(record_ids or [])]:
            if rid not in target_ids:
                target_ids.append(rid)
        if record_id not in target_ids:  # 防御：主记录永远在集合里
            target_ids.insert(0, record_id)
        extra_ids = [rid for rid in target_ids if rid != record_id]
        if record_ids is not None and record_id not in record_ids:
            raise PcsError(
                f"变更记录的集合必须包含路径里的记录 {record_id}",
                code="CHANGE_NOTICE_RECORD_SET_INVALID",
                status=422,
            )

        # 2c. 集合里**每一条**都要：存在 + CHANGED + 属于本项目 + 没有未关闭的变更单
        records: list[Any] = [record] if record is not None else []
        for rid in extra_ids:
            rec = await cls._check_record_charged(db, rid, record_table)
            rec_project_id = getattr(rec, "project_id", None)
            if rec_project_id is not None and rec_project_id != project_id:
                raise PcsError(
                    f"记录 {rid} 属于项目 {rec_project_id}，"
                    f"不能建到项目 {project_id} 名下",
                    code="CHANGE_NOTICE_PROJECT_MISMATCH",
                    status=422,
                )
            records.append(rec)

        # 3. 集合里任一条**已有未关闭的变更单** ⇒ 409（明说，不是撞唯一约束）
        #    ⚠️ 按 **binding** 找（而不是 scope_value）—— 多记录变更单的
        #    scope 只标识主记录 ⇒ 次要记录在 scope 里查不到 ⇒ 必须按 binding。
        #    「未关闭」= 交付物**不是** APPROVED（已批准的那张已经关过记录了）。
        for rid in target_ids:
            existing = await cls._find_open_notice_for_record(
                db, record_type=record_type_name, record_id=rid
            )
            if existing is not None:
                raise PcsError(
                    f"记录 {rid} 已有变更单 {existing.doc_no}"
                    f"（一条记录同时只在**一张未关闭**的变更单里）",
                    code="CHANGE_NOTICE_ALREADY_EXISTS",
                    status=409,
                )

        # 4. 签署矩阵（惰性建行 —— 没有它变更单建不出来）
        matrix = await SignatureMatrixService.ensure_change_notice_matrix(
            db, project_id=project_id
        )
        # ⚠️ 矩阵**没有可用步骤** ⇒ 422（明说）。
        # 否则变更单建出来了、观测行也写了 PENDING，但它**一步都签不了**
        # ⇒ 变更单永远停在「进行中」，而甘特图上却会一路走到 COMPLETED ——
        # 「看起来走完了，其实一步没签」。
        if not SignatureMatrixService.parse_steps(matrix):
            raise PcsError(
                f"签署矩阵 {matrix.matrix_name!r} 没有可用步骤"
                "（变更单需要 3 级校审才能推进）",
                code="SIGNATURE_MATRIX_INVALID",
                status=422,
            )

        # 5. 创建 deliverables 行（deliverable_type=CHANGE_NOTICE）
        # ⚠️ **编号取「变更单自己的」uuid**（不是记录的）—— 同上：一条记录可以
        #    有多张变更单 ⇒ 记录派生的编号会撞 `uq_deliverables_doc_no`
        #    ⇒ 未捕获的 IntegrityError（500）。
        #    完整 32 位 hex：前 8 位（32 bit）在同项目 ~65k 张单时就会撞 ⇒ 500。
        #    ⚠️ 这只是**唯一**，不是可读编号 —— 改走编号模板另批（TODO-073）。
        deliverable = Deliverable(
            deliverable_id=notice_id,
            project_id=project_id,
            deliverable_type="CHANGE_NOTICE",
            scope_type="CUSTOM",
            scope_value=scope_value,
            doc_no=f"CN-{notice_id.hex.upper()}",
            doc_no_mode="MANUAL",
            title=f"变更单 - {change_type.value}",
            current_rev="0",
            version_purpose="ISSUED_FOR_CHANGE",
            sign_status=DeliverableSignStatus.DRAFT,
            matrix_id=matrix.matrix_id,
        )
        db.add(deliverable)
        await db.flush()

        # 6. 创建 1:1 扩展 change_notice_details
        detail = ChangeNoticeDetail(
            deliverable_id=deliverable.deliverable_id,
            change_type=change_type.value,
            reason=reason,
            triggered_by=triggered_by.value,
            source_record_type=(record_table.__name__ if record_table else None),
        )
        db.add(detail)
        await db.flush()

        # 7. **建版本行**（ISSUED_FOR_CHANGE）—— 没有版本就进不了签署流程
        #    （`sign_step` 要 version_id）⇒ ADR-0008「一套版本历史」对变更单
        #    才成立。`create_version_row` **不 commit** ⇒ 与建单同一事务。
        version = await DeliverableService.create_version_row(
            db,
            deliverable=deliverable,
            version_purpose="ISSUED_FOR_CHANGE",
            actor_user_id=getattr(actor, "user_id", None),
            description=f"变更单版本（{change_type.value}）",
        )

        # 8. **绑定记录**（ADR-0008：`deliverable_record_bindings` 承载新旧哈希
        #    对比，替代原 `change_notice_record_bindings`）⇒ 记录↔变更单的
        #    权威关联在这里；`scope_value` 只是 scope（两者由守卫测试钉住一致）。
        # ⚠️ **每条记录一行 binding**（TODO-078：一次变更常影响多条记录）
        #    ⇒ 关闭时**批量**关（`close_on_approved`）。
        for rec in records:
            binding = DeliverableRecordBinding(
                deliverable_version_id=version.version_id,
                record_type=(record_table.__name__ if record_table else ""),
                record_id=cls._record_pk_of(rec),
                record_hash=(rec.record_hash or "") if rec is not None else "",
                old_record_hash_before_change=await cls._pre_change_hash(
                    db,
                    record_type=(record_table.__name__ if record_table else ""),
                    record_id=cls._record_pk_of(rec),
                ),
            )
            db.add(binding)
        if not records:
            # ⚠️ **没有 record_table**（查不到记录行）⇒ 仍写一行（record_type 空）
            #    —— 旧行为；此时 `close_on_approved` 会因找不到模型而**响亮失败**。
            db.add(
                DeliverableRecordBinding(
                    deliverable_version_id=version.version_id,
                    record_type="",
                    record_id=record_id,
                    record_hash="",
                    old_record_hash_before_change=None,
                )
            )
        await db.flush()

        # 9. ⚠️ **观测写入点 2a：变更单的「创建」**（ADR-0047 §① 🔒 service 层）
        #    写 PENDING：流程已发起、尚未关闭（不是 COMPLETED —— 那是关闭时写的）。
        #    `record_step` 不 commit ⇒ 与建单同一事务（观测写失败 ⇒ 建单回滚）。
        await record_step(
            session=db,
            project_id=project_id,
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=deliverable.deliverable_id,
            step_order=1,
            step_role="CHANGE_NOTICE",
            state=WorkflowProgressState.PENDING,
            actor_user_id=getattr(actor, "user_id", None),
        )

        # 10. 写 audit
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

        # 11. 返回轻量 DTO
        return {
            "deliverable_id": deliverable.deliverable_id,
            # ⚠️ **行里的真值**（不是常量）—— 建单时交付物被推进到 PENDING
            # （`create_version_row`），但那是**副作用**：万一它没推进，
            # 端点就不该报 PENDING（会骗用户说「在签署中」，而 sign-step 会 409）。
            "sign_status": deliverable.sign_status.value,
            # 签署要用的版本 id（矩阵的 3 级校审作用在它身上）
            "version_id": version.version_id,
            # 观测工作流的 id —— 与 SIGN 不同类（那是版本 id）
            "workflow_id": deliverable.deliverable_id,
            "matrix_id": matrix.matrix_id,
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
    async def refresh_open_bindings(
        cls,
        db: AsyncSession,
        *,
        record_type: str,
        record_id: uuid.UUID,
        record_hash: str,
        actor_user_id: uuid.UUID | None = None,
    ) -> int:
        """刷新该记录名下**未关闭**变更单的绑定哈希（TODO-086）。返回刷新了几行。

        ## 为什么需要这一步（否则关闭凭证说的不是被关的那条数据）

        「撤销 → 重来」的返工路径里，记录在 CHANGE_PENDING 期间**又被改了**
        ⇒ 记录的当前哈希与变更单建单时记下的**不是同一个** ⇒
        变更单被签完、关掉记录时，它声称「我关的是 hash=X 的那条数据」——
        而记录早就不是 hash=X 了 ⇒ **关闭凭证不可信**。

        ## 刷成什么

        - `record_hash` = 记录**当前**哈希（本次 apply-change 之后的）
        - `old_record_hash_before_change` = **本次**变更前的哈希
          = 最新 ACTIVE 的 BEFORE_CHANGE 快照哈希（与建单时**同一口径**
          ⇒ 复用 `_pre_change_hash`）

        ## 只刷「未关闭」的

        已 APPROVED 的变更单**已经关过记录**了 ⇒ 它的绑定描述的是**那一轮**
        的哈希 ⇒ 改它 = 篡改历史。

        ## 调用点

        `records_actions.apply_change`（CHANGE_PENDING → CHANGED）——
        那是记录**再次**变 CHANGED 的唯一入口 ⇒ 刷新的时机只有这一处。
        ⚠️ 与状态迁移**同一事务**（调用方在 commit 之前调本方法）。
        """
        rows = (
            await db.execute(
                select(DeliverableRecordBinding, Deliverable.deliverable_id)
                .join(
                    DeliverableVersion,
                    DeliverableVersion.version_id
                    == DeliverableRecordBinding.deliverable_version_id,
                )
                .join(
                    Deliverable,
                    Deliverable.deliverable_id == DeliverableVersion.deliverable_id,
                )
                .where(
                    DeliverableRecordBinding.record_type == record_type,
                    DeliverableRecordBinding.record_id == record_id,
                    Deliverable.deliverable_type == "CHANGE_NOTICE",
                    # ⚠️ 与 `_find_open_notice_for_record` **同一口径**：只有
                    #    「开着」（DRAFT/PENDING）的变更单需要刷新。
                    Deliverable.sign_status.in_(
                        [
                            DeliverableSignStatus.DRAFT.value,
                            DeliverableSignStatus.PENDING.value,
                        ]
                    ),
                )
            )
        ).all()
        if not rows:
            return 0

        old_hash = await cls._pre_change_hash(
            db, record_type=record_type, record_id=record_id
        )
        for binding, _deliverable_id in rows:
            binding.record_hash = record_hash
            binding.old_record_hash_before_change = old_hash
        await db.flush()

        await AuditService(db).write(
            action=AuditAction.CHANGE_NOTICE_BINDING_REFRESHED,
            resource_type="DELIVERABLE",
            resource_id=str(rows[0][1]),
            user_id=actor_user_id,
            detail={
                "record_type": record_type,
                "record_id": str(record_id),
                "record_hash": record_hash,
                "old_record_hash_before_change": old_hash,
                "refreshed_bindings": len(rows),
            },
        )
        return len(rows)

    @classmethod
    async def _pre_change_hash(
        cls,
        db: AsyncSession,
        *,
        record_type: str,
        record_id: uuid.UUID,
    ) -> str | None:
        """该记录最新 ACTIVE 的 BEFORE_CHANGE 快照里的哈希（没有 ⇒ None）。

        ⚠️ 查询形状与 `state_machine._restore_snapshot_if_needed` **一致**
        （同表、同过滤、同排序）—— 两处对「快照是什么」的判断若不同，
        就会一个恢复的是 A 快照、另一个记的是 B 快照的哈希。
        """
        snapshot = (
            await db.execute(
                select(RecordChangeSnapshot)
                .where(
                    RecordChangeSnapshot.record_type == record_type,
                    RecordChangeSnapshot.record_id == record_id,
                    RecordChangeSnapshot.snapshot_status == "ACTIVE",
                )
                .order_by(RecordChangeSnapshot.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return snapshot.record_hash if snapshot is not None else None

    @classmethod
    async def _notify_approved(cls, db, *, deliverable, detail) -> list[NotificationPayload]:
        """审批通过的通知触发（用户 2026-10-20 裁决的最小接线集合）。

        收件人 = 项目的 DESIGNER。**为什么不是「变更单的申请人」** ——
        `ChangeNoticeDetail` 上没有申请人字段（`triggered_by` 是
        `MANUAL`/`UPSTREAM_CHANGE` 这样的来源枚举，不是用户）。唯一有既定
        语义的受众是项目的设计人：记录状态因这次审批而变了，而他们要重新算。

        无人可通知时不额外 commit —— 多一次提交没有任何数据好处。
        """
        from app.models.notification import NotificationKind
        from app.services.notifications.notify import notify_role
        from app.services.notifications.payload import NotificationDetail

        return await notify_role(
            db,
            role="DESIGNER",
            kind=NotificationKind.CHANGE_NOTICE_APPROVED,
            title=f"变更单「{getattr(deliverable, 'title', '')}」已批准",
            body="变更已生效，绑定的记录状态已更新",
            detail=NotificationDetail(
                project_id=deliverable.project_id,
                deliverable_id=deliverable.deliverable_id,
                workflow_type="CHANGE_NOTICE",
                reason=detail.reason,
            ),
            project_id=deliverable.project_id,
        )

    @classmethod
    async def close_on_approved(
        cls,
        db: AsyncSession,
        *,
        deliverable: Deliverable,
        actor_user_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        """变更单被签到最后一步（APPROVED）⇒ **自动**关掉那条记录。

        ADR-0008：「变更单 APPROVED 后**系统自动**将绑定记录 CHANGED → CHECKED
        并写入 `change_resolved_by`；被驳回则回 DRAFT，绑定记录保持 CHANGED」。

        ## 为什么触发点在**签最后一步**那里，而不是另一个「审批」端点

        「自动」= 状态被推成 APPROVED 的那一刻 ⇒ 触发点必须在那儿
        （`DeliverableService.sign_step`）。另开一个审批端点 ⇒ 矩阵形同虚设
        （谁都能直接批准，3 级校审不生效）。

        ## 记录的关联从哪来

        `deliverable_record_bindings`（ADR-0008 指定）—— 按**交付物**找
        （不是按版本）：变更单被退回后重新签发会有第 2 个版本，但**记录还是
        那条记录** ⇒ 关联不能绑在单个版本上。

        Raises:
            PcsError 409 `CHANGE_NOTICE_RECORD_LINK_MISSING` —— 找不到记录
                （响亮失败：静默跳过 = 变更单批准了而记录永远停在 CHANGED）。
        """
        bindings = await cls._find_record_bindings(
            db, deliverable_id=deliverable.deliverable_id
        )
        if not bindings:
            raise PcsError(
                f"变更单 {deliverable.deliverable_id} 没有绑定记录"
                f"（deliverable_record_bindings 里找不到）",
                code="CHANGE_NOTICE_RECORD_LINK_MISSING",
                status=409,
            )

        # ⚠️ **批量关闭**（TODO-078：一次变更常影响多条记录）⇒ 逐条关，
        #    每条**各自**校验（还在不在 CHANGED / 模型认不认识 / 记录还在不在）。
        #    ⚠️ 任一条不合格 ⇒ **整批失败**（抛错 ⇒ 事务回滚 ⇒ 一条都不关）
        #    —— 半关半不关 = 一张单关了两条记录而另一条还开着。
        detail = await cls._get_detail_by_deliverable(db, deliverable.deliverable_id)
        closed: list[dict[str, Any]] = []
        for binding in bindings:
            model = await cls._record_model_by_class_name(binding.record_type)
            if model is None:
                raise PcsError(
                    f"变更单 {deliverable.deliverable_id} 绑定的记录类型 "
                    f"{binding.record_type!r} 不在 RECORD_TYPE_REGISTRY 里",
                    code="CHANGE_NOTICE_RECORD_TYPE_UNKNOWN",
                    status=409,
                )
            record = await db.get(model, binding.record_id)
            if record is None:
                raise PcsError(
                    f"变更单 {deliverable.deliverable_id} 绑定的记录 "
                    f"{binding.record_id} 不存在",
                    code="CHANGE_NOTICE_RECORD_NOT_FOUND",
                    status=409,
                )
            # ⚠️ 关之前先看它**还在不在 CHANGED**：记录在变更单签完前可能已被
            # 别处改过（如被弃用）⇒ 无条件写 CHECKED 会**复活一条已作废的记录**。
            if record.sign_status != RecordSignStatus9.CHANGED.value:
                raise PcsError(
                    f"变更单 {deliverable.deliverable_id} 绑定的记录 "
                    f"{binding.record_id} 当前 {record.sign_status}，"
                    f"不是 CHANGED（不能把它关成 CHECKED）",
                    code="CHANGE_NOTICE_RECORD_BAD_STATE",
                    status=409,
                )

            # CHANGED → CHECKED（关闭）+ 记录是谁关的
            record.sign_status = RecordSignStatus9.CHECKED.value
            record.change_resolved_at = datetime.now(UTC)
            record.change_resolved_by = str(actor_user_id)

            await AuditService(db).write(
                action=AuditAction.CHANGE_NOTICE_APPROVED,
                resource_type="DELIVERABLE",
                resource_id=str(deliverable.deliverable_id),
                user_id=actor_user_id,
                detail={
                    "from": "CHANGED",
                    "to": "CHECKED",
                    "record_type": binding.record_type,
                    "record_id": str(binding.record_id),
                    "change_type": getattr(detail, "change_type", None),
                    "project_id": str(deliverable.project_id),
                },
            )
            closed.append(
                {
                    "record_type": binding.record_type,
                    "record_id": str(binding.record_id),
                    "from": "CHANGED",
                    "to": "CHECKED",
                }
            )

        # ⚠️ **观测写入点 2b 的新位置**：变更单**被签完**（不是「被批准」）⇒
        #    CHANGE_NOTICE 工作流走到 COMPLETED（与 ADR-0047 §① 一致）。
        #    ⚠️ 只写**一行**（工作流 = 变更单，不是记录）—— 多记录变更单
        #    仍然只有**一个** CHANGE_NOTICE 工作流。
        await record_step(
            session=db,
            project_id=deliverable.project_id,
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=deliverable.deliverable_id,
            step_order=1,
            step_role="CHANGE_NOTICE",
            state=WorkflowProgressState.COMPLETED,
            actor_user_id=actor_user_id,
        )

        # ⚠️ **通知行**（审批通过的受众 = 项目的 DESIGNER）—— 与业务变更**同一
        #    事务**写，**推送交给调用方**（`sign_step` 在 commit 之后推）。
        #    ⚠️ 此前这段逻辑在**已弃用**的 `approve_change_notice` 里 ⇒ 真实
        #    路径（sign_step → close_on_approved）**不通知任何人**（TODO-080
        #    第 2 条 ⇒ 随该方法一起迁到这条真实路径上）。
        pending_notifications = await cls._notify_approved(
            db, deliverable=deliverable, detail=detail
        )
        return {
            # ⚠️ 形状**向后兼容**（单记录时与旧版逐字一致）：第一条记录 +
            #     全部被关的记录（多记录变更单用）。
            "record_type": closed[0]["record_type"],
            "record_id": closed[0]["record_id"],
            "from": "CHANGED",
            "to": "CHECKED",
            "closed_records": closed,
            # ⚠️ **通知载荷**：由调用方（sign_step）在 commit **之后**推送
            #   （提交前推送 ⇒ commit 失败时用户收到会被回滚的通知）。
            "pending_notifications": pending_notifications,
        }

    @staticmethod
    def _record_pk_of(record: Any) -> uuid.UUID:
        """取记录行的主键（各表主键名不同：`relief_id` / `result_id` / `id` …）。"""
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(record.__class__)
        pk = mapper.primary_key[0]
        val = getattr(record, pk.name)
        if not isinstance(val, uuid.UUID):
            raise PcsError(
                f"记录主键必须是 UUID，拿到 {type(val).__name__}",
                code="CHANGE_NOTICE_RECORD_PK_INVALID",
                status=500,
            )
        return val

    @classmethod
    async def cancel_change_notice(
        cls,
        db: AsyncSession,
        *,
        record_type: str,
        record_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        reason: str,
    ) -> dict[str, Any]:
        """作废该记录当前**开着**的那张变更单（TODO-069 第 2 条 / TODO-080 第 1 条）。

        ## 为什么需要

        驳回（RETURN）只是让变更单回 DRAFT ⇒ 它**还开着** ⇒ 该记录**仍然**
        被它占着（「一条记录同时只在**一张未关闭**的变更单里」）⇒ 用户想
        「作废这张单、另起一张」**没有路**⇒ 而变更单**没有取消路径** ⇒
        「已取消的单不挡新单」这条规则永远无从验证。

        ## 作废 = 交付物 `sign_status = OBSOLETE`

        交付物签审状态 4 态里已有 **OBSOLETE（已作废）** ⇒ **不需要迁移**。
        ⚠️ 与 `APPROVED` 一样：**作废的单不挡新单**（`_find_open_notice_for_record`
        只认 DRAFT / PENDING）。

        ## 记录怎么办

        **不动**（保持 CHANGED）—— 作废的是**单据**，不是**校核结论**：
        记录仍在等一个关闭凭证 ⇒ 用户可以**重新建单**（现在路通了）或
        **撤销**（request-reversal ⇒ 恢复快照 ⇒ CHECKED ⇒ 重来）。
        ⚠️ 若「作废」顺手把记录关成 CHECKED ⇒ 等于**绕过 3 级校审** ⇒ 不做。

        Raises:
            PcsError 404 `CHANGE_NOTICE_NOT_FOUND` —— 该记录没有开着的变更单
            PcsError 409 `CHANGE_NOTICE_ALREADY_CLOSED` —— 已 APPROVED / 已作废
        """
        if not reason or not reason.strip():
            raise PcsError(
                "作废变更单必须填写理由",
                code="CHANGE_NOTICE_CANCEL_REASON_REQUIRED",
                status=422,
            )

        notice = await cls._find_open_notice_for_record(
            db, record_type=record_type, record_id=record_id
        )
        if notice is None:
            raise PcsError(
                f"记录 {record_id} 没有开着的变更单（可作废的只有 DRAFT/PENDING 的）",
                code="CHANGE_NOTICE_NOT_FOUND",
                status=404,
            )

        notice.sign_status = DeliverableSignStatus.OBSOLETE
        await db.flush()

        await AuditService(db).write(
            action=AuditAction.CHANGE_NOTICE_CANCELLED,
            resource_type="DELIVERABLE",
            resource_id=str(notice.deliverable_id),
            user_id=actor_user_id,
            detail={
                "record_type": record_type,
                "record_id": str(record_id),
                "reason": reason,
                "doc_no": notice.doc_no,
                "project_id": str(notice.project_id),
            },
        )

        # ⚠️ 观测：CHANGE_NOTICE 工作流**没有走完** ⇒ FAILED（与签署被退回
        #    同口径：sign_step 的 RETURN 也写 FAILED）。
        await record_step(
            session=db,
            project_id=notice.project_id,
            workflow_type=WorkflowType.CHANGE_NOTICE,
            workflow_id=notice.deliverable_id,
            step_order=1,
            step_role="CHANGE_NOTICE",
            state=WorkflowProgressState.FAILED,
            actor_user_id=actor_user_id,
        )

        return {
            "deliverable_id": str(notice.deliverable_id),
            "doc_no": notice.doc_no,
            "record_type": record_type,
            "record_id": str(record_id),
            "sign_status": DeliverableSignStatus.OBSOLETE.value,
        }

    @classmethod
    async def _find_open_notice_for_record(
        cls,
        db: AsyncSession,
        *,
        record_type: str,
        record_id: uuid.UUID,
    ) -> Deliverable | None:
        """按**记录**找它当前所在的那张**未关闭**变更单（没有 ⇒ None）。

        ⚠️ **按 binding 找**（不是按 `scope_value`）：多记录变更单的 scope
        只标识**主记录** ⇒ 次要记录在 scope 里查不到 ⇒ 只能按 binding 查。

        ⚠️ 「未关闭」= 交付物**不是** `APPROVED` —— 已批准的那张**已经关过
        记录了**（记录回到 CHECKED）⇒ 不该再挡住新变更单。
        """
        return (
            await db.execute(
                select(Deliverable)
                .join(
                    DeliverableVersion,
                    DeliverableVersion.deliverable_id == Deliverable.deliverable_id,
                )
                .join(
                    DeliverableRecordBinding,
                    DeliverableRecordBinding.deliverable_version_id
                    == DeliverableVersion.version_id,
                )
                .where(
                    DeliverableRecordBinding.record_type == record_type,
                    DeliverableRecordBinding.record_id == record_id,
                    Deliverable.deliverable_type == "CHANGE_NOTICE",
                    # ⚠️ 「**开着**」= DRAFT / PENDING —— **不是** APPROVED（已关过
                    #    记录）也**不是** OBSOLETE（已作废，TODO-080 第 1 条）。
                    Deliverable.sign_status.in_(
                        [
                            DeliverableSignStatus.DRAFT.value,
                            DeliverableSignStatus.PENDING.value,
                        ]
                    ),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

    @classmethod
    async def _find_record_bindings(
        cls, db: AsyncSession, *, deliverable_id: uuid.UUID
    ) -> list[DeliverableRecordBinding]:
        """按**交付物**找它绑的**全部**记录（不按版本 —— 见 `close_on_approved`）。

        ⚠️ **多行**（TODO-078）：一次变更常影响多条记录 ⇒ binding 写多行 ⇒
        关闭时**批量**关。
        """
        rows = (
            await db.execute(
                select(DeliverableRecordBinding)
                .join(
                    DeliverableVersion,
                    DeliverableRecordBinding.deliverable_version_id
                    == DeliverableVersion.version_id,
                )
                .where(DeliverableVersion.deliverable_id == deliverable_id)
            )
        ).scalars().all()
        # ⚠️ **去重**（按 record_id）：变更单重新签发会有多个版本 ⇒ 同一个
        #    版本可能被 join 命中多次 ⇒ 不去重会把同一条记录关两遍。
        seen: set[uuid.UUID] = set()
        unique: list[DeliverableRecordBinding] = []
        for row in rows:
            if row.record_id in seen:
                continue
            seen.add(row.record_id)
            unique.append(row)
        return unique

    @staticmethod
    async def _record_model_by_class_name(name: str) -> type | None:
        """记录类型的**类名** → ORM 模型。

        ⚠️ 按**类名**找而不是按注册表的键：`RECORD_TYPE_REGISTRY` 的键风格
        不统一（`PipingResult` / `cv_result` 混着），而 binding 里存的是
        ORM 类名 ⇒ 按键找会漏。
        """
        from app.services.calc_lineage import RECORD_TYPE_REGISTRY

        for model in RECORD_TYPE_REGISTRY.values():
            if getattr(model, "__name__", None) == name:
                return model
        return None

__all__ = [
    "ChangeNoticeService",
    "ChangeType",
    "TriggeredBy",
    "ALLOWED_CHANGE_TYPES",
]
