"""交付物读服务（P1-7+ D 模块 / P8 前置）。

P8 REPORT 的实际依赖是「从 `deliverables` / `deliverable_versions` 读数据」——
`docs/PCS-NOTE-P8前置清单与3项修订-2026-10-07.md` ② 列出该缺口时，确认现状是
**有 9 个模型、有 ChangeNoticeService，但无 service / schema / API**。

P9A B lane 起本服务**同时承载写面**：`issue`（本轮）→ `sign_step`（B2）→
代录（B3）。写面放在这里而不是新建 service，是因为签署流程的所有读写都围着
`deliverables` / `deliverable_versions` 两张表转，拆开只会让同一个事务跨两个 service。

## 仍不在本轮实现的写端点

`POST /deliverables`（创建）与 `POST /deliverables/{id}/customer-approval/proxy`
（B3）。前者 P9A 范围外（现有 doc_no 由既有流程给定），后者待 B3。

## 事务写法

跟随同族的 `change_notice_service`（同为交付物表族的写 service）：显式
`await db.commit()`，不用 `commit_or_rollback`。ADR-0047 §尚未解决 的
「以该写入点所在 service 内的邻近代码为准」规则在这里的裁决依据即此。
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.config_domain import NumberingTemplate
from app.models.deliverable import (
    CustomerApprovalAttachment,
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
    ProjectSignatureMatrixBinding,
    SignatureMatrix,
)
from app.models.enums import (
    AuditAction,
    DeliverableSignStatus,
    WorkflowProgressState,
    WorkflowType,
)
from app.models.project import Project
from app.models.system import AuditLog
from app.models.workflow_progress import WorkflowProgress
from app.services.audit_service import AuditService
from app.services.notifications.notify import publish
from app.services.notifications.payload import NotificationPayload
from app.services.numbering_service import NumberingService
from app.services.secondary_auth import verify_secondary_auth
from app.services.signature_matrix_service import SignatureMatrixService
from app.services.workflow_progress_writer import record_step

#: `segments_json` 里已登记的占位符（P2 计划设计 §3.5 的示例段名）。
#: 匹配「标识符形状」（小写 + 下划线）的段一律按占位符解析，
#: 解析不到 ⇒ 报错；其余（`-` / `/` 等）按字面量原样拼接。
_TOKEN_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")


def _utcnow() -> datetime:
    return datetime.now(UTC)


#: 凭证附件大小上限 20 MB（SPEC P9A-DLV-008 / ADR-0007）。
#: 在**读进内存之前**判大小：先读后判的话，一个超大文件会先把进程打死。
_MAX_CREDENTIAL_BYTES = 20 * 1024 * 1024


def _read_credential(file_path: str) -> tuple[bytes, str]:
    """读凭证文件并算 SHA-256。路径逃逸由 `resolve_path` 拦（400）。

    Returns:
        `(内容, sha256 十六进制)`。
    """
    from app.services.report import paths as report_paths

    target = report_paths.resolve_path(file_path)  # 逃逸 ⇒ PcsError 400
    if not target.is_file():
        raise PcsError(
            code="PROXY_ATTACHMENT_MISSING",
            message=f"凭证文件不存在：{file_path}",
            status=400,
        )
    size = target.stat().st_size
    if size > _MAX_CREDENTIAL_BYTES:
        raise PcsError(
            code="PROXY_ATTACHMENT_TOO_LARGE",
            message=f"凭证文件 {size} 字节，超过 {_MAX_CREDENTIAL_BYTES} 上限",
            status=400,
        )
    payload = target.read_bytes()
    return payload, hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class SignStepOutcome:
    """`sign_step` 的返回值 —— API 层据此组装响应。

    刻意不返回 ORM 对象给 API 直接序列化：响应模型显式声明（P9A-DLV-010），
    ORM 上多一列就会自动多一字段，那是零裸字段约束要防的事。
    """

    deliverable: Deliverable
    version: DeliverableVersion
    step_index: int
    step_role: str
    decision: str
    state: WorkflowProgressState
    signed_at: datetime


@dataclass(frozen=True)
class CustomerApprovalProxyOutcome:
    """`record_customer_approval_proxy` 的返回值。"""

    deliverable: Deliverable
    version: DeliverableVersion
    attachment: CustomerApprovalAttachment
    signed_at: datetime



class DeliverableService:
    """交付物读写面。全部 classmethod，与 ChangeNoticeService 同风格。"""

    @classmethod
    async def list_by_project(
        cls,
        db: AsyncSession,
        *,
        project_id: uuid.UUID,
        deliverable_type: str | None = None,
        sign_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Deliverable], int]:
        """列项目下交付物 + 总数。

        Args:
            deliverable_type: 过滤。不传则含变更单（deliverable_type=CHANGE_NOTICE）。
            sign_status: 过滤签署状态。

        Returns:
            (交付物列表, 总数)。总数单独查而不复用 len(items) —— 列表有 limit。
        """
        conditions = [Deliverable.project_id == project_id]
        if deliverable_type:
            conditions.append(Deliverable.deliverable_type == deliverable_type)
        if sign_status:
            conditions.append(Deliverable.sign_status == sign_status)

        total = await db.scalar(
            select(func.count()).select_from(Deliverable).where(*conditions)
        )
        rows = (
            await db.execute(
                select(Deliverable)
                .where(*conditions)
                # ⚠️ 必须带 tiebreaker: created_at 是 server_default=func.now(),
                # SQLite 下 CURRENT_TIMESTAMP 只有**秒级**粒度 —— 同一批写入的行
                # 时间戳必然相同，只按 created_at 排序时并列行的返回顺序不确定。
                .order_by(
                    Deliverable.created_at.desc(),
                    Deliverable.doc_no,
                    Deliverable.deliverable_id,
                )
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    @classmethod
    async def current_version_ids(
        cls,
        db: AsyncSession,
        *,
        deliverables: Sequence[Deliverable],
    ) -> dict[uuid.UUID, uuid.UUID]:
        """一批交付物的「当前版本 id」= **`rev == current_rev`** 的那条版本行。

        ⚠️ **一次查询**（`deliverable_id IN (...)`）—— 序列化时逐行查版本就是
        N+1（行数一多，查询数跟着线性涨）。
        ⚠️ 传**行**而不是 id：判据需要 `current_rev`，而它住在交付物行上
        ⇒ 传行就**不用**再查一次交付物表（查询数仍是 3：计数 + 交付物 + 版本）。
        ⚠️ 匹配不到（没有版本行 / 没有同 Rev 的版本）⇒ **不进 dict**
        ⇒ 调用方 `.get()` 得 None（**不猜**「最近的那个」）。

        Args:
            deliverables: 已查出的交付物行（**不要**在这里再查一遍）。

        Returns:
            `{deliverable_id: version_id}` —— 只含**匹配上**的。
        """
        if not deliverables:
            return {}
        revs = {d.deliverable_id: d.current_rev for d in deliverables}
        rows = (
            await db.execute(
                select(
                    DeliverableVersion.deliverable_id,
                    DeliverableVersion.version_id,
                    DeliverableVersion.rev,
                )
                .where(
                    DeliverableVersion.deliverable_id.in_(
                        list(revs.keys())
                    )
                )
                # ⚠️ 必须带 tiebreaker：deliverable_versions 上**没有**
                # (deliverable_id, rev) 唯一约束 ⇒ 同一 Rev 可能有多行版本
                # ⇒ 不排序时「取哪一行」不确定，列表每次返回的 version_id 可能不同。
                .order_by(
                    DeliverableVersion.created_at,
                    DeliverableVersion.version_id,
                )
            )
        ).all()
        out: dict[uuid.UUID, uuid.UUID] = {}
        for deliverable_id, version_id, rev in rows:
            if rev == revs.get(deliverable_id) and deliverable_id not in out:
                out[deliverable_id] = version_id
        return out

    @classmethod
    async def get_or_404(
        cls, db: AsyncSession, *, deliverable_id: uuid.UUID
    ) -> Deliverable:
        """取交付物，不存在抛 404。

        注意：**不校验 project_id**。项目级访问权由 API 层
        `check_project_access_or_404` 先做（它用 404 而非 403 是为了不泄漏
        项目存在性），此处再抛一次 404 不会额外泄漏信息。
        """
        row = await db.get(Deliverable, deliverable_id)
        if row is None:
            raise PcsError(
                code="DELIVERABLE_NOT_FOUND",
                message=f"交付物 {deliverable_id} 不存在",
                status=404,
            )
        return row

    @classmethod
    async def list_versions(
        cls, db: AsyncSession, *, deliverable_id: uuid.UUID
    ) -> list[DeliverableVersion]:
        """Rev 历史，按 Rev 倒序（当前 Rev 在最前）。

        先确认交付物存在 —— 否则一个不存在的 deliverable_id 会返回空列表，
        与「存在但还没有版本」无法区分。
        """
        await cls.get_or_404(db, deliverable_id=deliverable_id)
        rows = (
            await db.execute(
                select(DeliverableVersion)
                .where(DeliverableVersion.deliverable_id == deliverable_id)
                # 同 list_by_project: created_at 秒级粒度，并列时必须靠
                # version_id 兜底，否则同一份数据多次调用返回顺序不同。
                .order_by(
                    DeliverableVersion.created_at.desc(),
                    DeliverableVersion.version_id,
                )
            )
        ).scalars().all()
        return list(rows)

    @classmethod
    async def get_snapshot(
        cls, db: AsyncSession, *, deliverable_id: uuid.UUID, rev: str
    ) -> dict[str, Any]:
        """取某 Rev 的快照 + 记录绑定明细（spec §3.2 的 snapshot 端点）。

        绑定明细走 `deliverable_record_bindings`，按 `record_type` + `record_id`
        排序以保证多次调用顺序稳定 —— 报表要按顺序渲染，不能靠 DB 返回顺序。
        """
        await cls.get_or_404(db, deliverable_id=deliverable_id)

        version = (
            await db.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == deliverable_id,
                    DeliverableVersion.rev == rev,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            raise PcsError(
                code="DELIVERABLE_REV_NOT_FOUND",
                message=f"交付物 {deliverable_id} 没有 Rev {rev}",
                status=404,
            )

        bindings = (
            await db.execute(
                select(DeliverableRecordBinding)
                .where(
                    DeliverableRecordBinding.deliverable_version_id == version.version_id
                )
                .order_by(
                    DeliverableRecordBinding.record_type,
                    DeliverableRecordBinding.record_id,
                )
            )
        ).scalars().all()

        deliverable = await cls.get_or_404(db, deliverable_id=deliverable_id)
        return {
            "deliverable": deliverable,
            "version": version,
            "bindings": list(bindings),
        }

    # ------------------------------------------------------------------
    # 写面（P9A B1：issue）
    # ------------------------------------------------------------------

    @classmethod
    async def issue(
        cls,
        db: AsyncSession,
        *,
        deliverable_id: uuid.UUID,
        version_purpose: str,
        actor_user_id: uuid.UUID,
        description: str = "",
    ) -> DeliverableVersion:
        """签发一个新版本（SPEC P9A-DLV-001/002/003）。

        步骤：
        1. 矩阵必须**真的绑在这个项目上**（`project_signature_matrix_bindings`）——
           `Deliverable.matrix_id` 是 NOT NULL，但 NOT NULL 只保证有值，
           不保证这个矩阵是这个项目选的。
        2. 幂等：同一 (deliverable, version_purpose) 已有版本 ⇒ 409。
        3. 编号：绑了 `numbering_template_id` 才重新取号，否则保留创建时的号。
        4. rev = 已有版本里最大的整数号 + 1（首个为 1）。
        5. 建版本行 + 推进交付物（DRAFT → PENDING，current_rev/version_purpose 跟随）
           + 写审计，**同一事务** commit。

        Returns:
            新建的 `DeliverableVersion` 行。
        """
        deliverable = await cls.get_or_404(db, deliverable_id=deliverable_id)

        await cls._assert_matrix_bound(db, deliverable=deliverable)

        duplicated = (
            await db.execute(
                select(DeliverableVersion).where(
                    DeliverableVersion.deliverable_id == deliverable_id,
                    DeliverableVersion.version_purpose == version_purpose,
                )
            )
        ).scalar_one_or_none()
        # ⚠️ 幂等判据 =「有**未退回**的版本」，不是「有版本」。
        # 交付物退回后（`sign_step` 的 RETURN ⇒ DRAFT）必须能**重新签发**：
        # 否则变更单被驳回一次就**永久卡死**（DRAFT ⇒ sign-step 409、
        # issue 409 ⇒ 永远签不了）。
        if duplicated is not None and deliverable.sign_status != DeliverableSignStatus.DRAFT:
            raise PcsError(
                code="DELIVERABLE_ALREADY_ISSUED",
                message=(
                    f"交付物 {deliverable_id} 已有版本目的 {version_purpose} 的版本"
                    f"（rev={duplicated.rev}）"
                ),
                status=409,
            )

        doc_no = await cls._allocate_doc_no(db, deliverable=deliverable)

        version = await cls.create_version_row(
            db,
            deliverable=deliverable,
            version_purpose=version_purpose,
            actor_user_id=actor_user_id,
            description=description,
        )
        deliverable.doc_no = doc_no

        await AuditService(db).write(
            action=AuditAction.DELIVERABLE_ISSUED,
            resource_type="deliverable",
            resource_id=deliverable_id,
            user_id=actor_user_id,
            detail={
                "rev": version.rev,
                "version_purpose": version_purpose,
                "doc_no": doc_no,
            },
        )

        await db.commit()
        await db.refresh(version)
        return version

    @classmethod
    async def create_version_row(
        cls,
        db: AsyncSession,
        *,
        deliverable: Deliverable,
        version_purpose: str,
        actor_user_id: uuid.UUID | None,
        description: str = "",
    ) -> DeliverableVersion:
        """建版本行 + 把交付物推进到签署中（PENDING）。**不 commit。**

        ## 为什么单独拆出来

        `issue` 是「签发」这个**用户动作**：它自己审计、自己提交。
        而变更单建单需要「交付物 + 版本 + 记录绑定 + 观测」在**同一事务**里
        （ADR-0047 §②③：观测写失败 ⇒ 业务变更一起回滚）⇒ 不能调一个会
        自己 commit 的方法。

        ⇒ 事务边界归调用方：`issue` = 本方法 + 审计 + commit；
        `ChangeNoticeService.create_change_notice` = 本方法 + 绑定 + 观测 +
        审计 + **一次** commit。

        ⚠️ 调用方负责「矩阵已绑到本项目」的校验（`issue` 走 `_assert_matrix_bound`；
        变更单走 `ensure_change_notice_matrix`，绑定在同一事务里建出来）。
        """
        matrix = await db.get(SignatureMatrix, deliverable.matrix_id)
        # ⚠️ 快照里写**归一化后**的步骤（排序 / 过滤 / 缺省补齐），不是原始
        # `steps_json` —— 否则快照显示的顺序与实际签署顺序不一致（顺序乱的矩阵
        # ⇒ 快照 A/B/C、签署按 C/A/B 推进），而 `steps_json` 的原始值还对外可见
        # （`GET /deliverables/{id}/snapshot`）。
        steps = (
            [
                {
                    "step_order": s.step_order,
                    "sign_role": s.sign_role,
                    "required": s.required,
                    "can_self_check": s.can_self_check,
                    "can_skip": s.can_skip,
                }
                for s in SignatureMatrixService.parse_steps(matrix)
            ]
            if matrix is not None
            else []
        )
        rev = await cls._next_rev(db, deliverable_id=deliverable.deliverable_id)

        version = DeliverableVersion(
            deliverable_id=deliverable.deliverable_id,
            rev=rev,
            version_purpose=version_purpose,
            description=description or f"签发版本 rev={rev}（{version_purpose}）",
            # 记录绑定在 B4 的 submit-approval / 快照固化里补；签发时只有矩阵步骤。
            record_snapshot_json={"record_count": 0},
            signature_summary_json={
                "matrix_id": str(deliverable.matrix_id),
                "steps": steps,
            },
            created_by=actor_user_id,
        )
        db.add(version)

        deliverable.current_rev = rev
        deliverable.version_purpose = version_purpose
        deliverable.sign_status = DeliverableSignStatus.PENDING
        await db.flush()
        return version

    @classmethod
    async def _assert_matrix_bound(
        cls, db: AsyncSession, *, deliverable: Deliverable
    ) -> None:
        """矩阵未绑到本项目 ⇒ 409。

        NOT NULL 的 `matrix_id` 只保证「有矩阵」，不保证「是这个项目选的矩阵」。
        缺这一步，一个手工塞进 matrix_id 的行就能按别的项目的签署矩阵走流程。
        """
        binding = (
            await db.execute(
                select(ProjectSignatureMatrixBinding.binding_id).where(
                    ProjectSignatureMatrixBinding.project_id
                    == deliverable.project_id,
                    ProjectSignatureMatrixBinding.matrix_id == deliverable.matrix_id,
                )
            )
        ).scalar_one_or_none()
        if binding is None:
            raise PcsError(
                code="DELIVERABLE_MATRIX_UNBOUND",
                message=(
                    f"项目 {deliverable.project_id} 未绑定签署矩阵 "
                    f"{deliverable.matrix_id}，不能签发"
                ),
                status=409,
            )

    @classmethod
    async def _allocate_doc_no(
        cls, db: AsyncSession, *, deliverable: Deliverable
    ) -> str:
        """按编号模板分配 doc_no；未绑模板 ⇒ 原样返回既有 doc_no（P9A-DLV-003）。

        序号取自 `NumberingService.next_value`（`SELECT ... FOR UPDATE` 行锁，
        PG 串行化同 scope 并发取号）—— **不得**改成 `max(doc_no)+1`，
        后者在并发下必然撞号，而撞号意味着两份交付物对外同号。
        """
        if deliverable.numbering_template_id is None:
            return deliverable.doc_no

        template = await db.get(NumberingTemplate, deliverable.numbering_template_id)
        if template is None:
            raise PcsError(
                code="NUMBERING_TEMPLATE_NOT_FOUND",
                message=f"编号模板 {deliverable.numbering_template_id} 不存在",
                status=409,
            )

        # scope 取 deliverable_type：同项目同类型共享一条序列，
        # 不同类型的号段互不干扰（否则 CALCULATION_BOOK 会吃掉 PUMP_DATASHEET 的号）。
        seq = await NumberingService(db).next_value(
            deliverable.project_id, template.template_id, deliverable.deliverable_type
        )

        project = await db.get(Project, deliverable.project_id)
        tokens = {
            "project_no": project.project_no if project is not None else "",
            "doc_type": deliverable.deliverable_type,
            "seq": str(seq),
        }
        # `segments_json` 的真实内容是**列表**（P2 计划设计 §3.5：
        # `["project_no","-","doc_type","-","seq"]`），但模型把它标成了 `Mapped[dict]`
        # —— 那个标注是错的（P8 遗留）。此处用 Any 而不去改模型标注：
        # 改它会牵动别的消费者，而它不在本轮范围内。已登记待修。
        segments: Any = template.segments_json or []
        parts: list[str] = []
        for segment in segments:
            if not isinstance(segment, str):
                raise PcsError(
                    code="NUMBERING_TEMPLATE_INVALID",
                    message=f"编号模板段必须是字符串，实际 {segment!r}",
                    status=400,
                )
            if segment in tokens:
                parts.append(tokens[segment])
            elif _TOKEN_SHAPE.match(segment):
                # 标识符形状但未登记 ⇒ 模板写错。**不能当字面量输出**：
                # `projct_no`（拼错）会被渲染成 `projct_no-1` 这种看着像编号、
                # 实则永不变的垃圾号，且没人知道为什么全项目撞号。
                raise PcsError(
                    code="NUMBERING_TEMPLATE_UNKNOWN_TOKEN",
                    message=(
                        f"编号模板含未登记的段 {segment!r}；"
                        f"已登记：{sorted(tokens)}"
                    ),
                    status=400,
                )
            else:
                parts.append(segment)
        return "".join(parts)

    @classmethod
    async def _next_rev(cls, db: AsyncSession, *, deliverable_id: uuid.UUID) -> str:
        """下一个 rev：已有版本里最大整数号 + 1（无版本则 1）。

        0 是草稿位不是版本号，故首个签发版本是 1。`current_rev` 的取值词表
        含 'A'/'B'/'X' 等字母版本 —— 那些不参与计数，按 0 忽略；
        真要用字母版本时要另开一条规则（TODO 登记在 P9B 的 Rev 生成器）。
        """
        revs = (
            await db.execute(
                select(DeliverableVersion.rev).where(
                    DeliverableVersion.deliverable_id == deliverable_id
                )
            )
        ).scalars().all()
        numeric = [int(r) for r in revs if r.isdigit()]
        return str(max(numeric, default=0) + 1)

    # ------------------------------------------------------------------
    # 写面（P9A B2：sign_step + 观测写入点 ①）
    # ------------------------------------------------------------------

    @classmethod
    async def sign_step(
        cls,
        db: AsyncSession,
        *,
        deliverable_id: uuid.UUID,
        version_id: uuid.UUID,
        step_index: int,
        decision: str,
        actor_user_id: uuid.UUID,
        actor_role: str,
    ) -> SignStepOutcome:
        """推进签署矩阵的一步（SPEC P9A-DLV-007）。

        这是 `SignatureMatrix.steps_json` 的第一个消费方。步骤只能**顺序**推进：
        越步签 409 —— 否则矩阵的职责分离失效（复核人能在设计人没签时先签复核）。

        同时经 `workflow_progress_writer.record_step` 写观测行（ADR-0047 §① 🔒）：
        ① 本步的终态（COMPLETED / FAILED / SKIPPED）
        ② 下一步的 IN_PROGRESS（最后一步则不写）
        甘特图就是这两行拼出来的。

        Returns:
            `SignStepOutcome`（供 API 层组装响应）。

        Raises:
            PcsError 404 `SIGN_STEP_NOT_FOUND` / 403 `SIGN_STEP_ROLE_MISMATCH` /
                403 `SIGN_STEP_SELF_CHECK_FORBIDDEN` / 409 `SIGN_STEP_OUT_OF_ORDER` /
                409 `SIGN_STEP_NOT_IN_APPROVAL` / 409 `SIGN_STEP_SKIP_FORBIDDEN`
        """
        deliverable = await cls.get_or_404(db, deliverable_id=deliverable_id)
        version = await db.get(DeliverableVersion, version_id)
        if version is None or version.deliverable_id != deliverable_id:
            raise PcsError(
                code="SIGN_STEP_NOT_FOUND",
                message=f"交付物 {deliverable_id} 下没有版本 {version_id}",
                status=404,
            )
        if deliverable.sign_status != DeliverableSignStatus.PENDING:
            raise PcsError(
                code="SIGN_STEP_NOT_IN_APPROVAL",
                message=(
                    f"交付物 {deliverable_id} 当前状态 "
                    f"{deliverable.sign_status.value}，不在签署中"
                ),
                status=409,
            )

        matrix = await db.get(SignatureMatrix, deliverable.matrix_id)
        steps = cls._matrix_steps(matrix)
        if step_index > len(steps):
            raise PcsError(
                code="SIGN_STEP_NOT_FOUND",
                message=f"签署矩阵只有 {len(steps)} 步，第 {step_index} 步不存在",
                status=404,
            )
        step = steps[step_index - 1]

        await cls._assert_step_order(db, workflow_id=version_id, step=step, steps=steps)

        sign_role = str(step.get("sign_role", ""))
        if sign_role != actor_role:
            raise PcsError(
                code="SIGN_STEP_ROLE_MISMATCH",
                message=f"第 {step_index} 步要求角色 {sign_role}，当前角色 {actor_role}",
                status=403,
            )
        if not step.get("can_self_check", True) and version.created_by == actor_user_id:
            raise PcsError(
                code="SIGN_STEP_SELF_CHECK_FORBIDDEN",
                message=(
                    f"第 {step_index} 步不允许自校（矩阵 can_self_check=false），"
                    f"提交人不得签自己的版本"
                ),
                status=403,
            )

        if decision == "SKIP" and not step.get("can_skip", False):
            raise PcsError(
                code="SIGN_STEP_SKIP_FORBIDDEN",
                message=f"签署矩阵未允许跳过第 {step_index} 步（can_skip=false）",
                status=409,
            )

        now = _utcnow()
        state = {
            "SIGN": WorkflowProgressState.COMPLETED,
            "RETURN": WorkflowProgressState.FAILED,
            "SKIP": WorkflowProgressState.SKIPPED,
        }[decision]

        next_step = steps[step_index] if step_index < len(steps) else None
        if decision == "SIGN" and next_step is None:
            deliverable.sign_status = DeliverableSignStatus.APPROVED
            # ⚠️ **变更单的最后一步 ⇒ 自动关记录**（ADR-0008：「变更单 APPROVED
            # 后**系统自动**将绑定记录 CHANGED → CHECKED 并写入
            # `change_resolved_by`」）。
            # 触发点必须在这儿（把状态推成 APPROVED 的那一刻）—— 另开一个
            # 「审批」端点 ⇒ 3 级矩阵形同虚设（谁都能直接批准）。
            # ⚠️ 懒导入：change_notice_service 要 import 本模块（建版本），
            # 模块级互相 import 会成环。
            if deliverable.deliverable_type == "CHANGE_NOTICE":
                from app.services.change_notice_service import ChangeNoticeService

                await ChangeNoticeService.close_on_approved(
                    db,
                    deliverable=deliverable,
                    actor_user_id=actor_user_id,
                )
        elif decision == "RETURN":
            # 退回 = 交付物整体回草稿。后续要改内容必须重新 issue 出新版本，
            # 不能在原版本上继续推进 —— 否则退回的理由会挂在已签过的版本上。
            # ADR-0008：「被驳回则回 DRAFT，**绑定记录保持 CHANGED**」——
            # 这里**不碰记录** ✔（记录要到变更单被签完才关）。
            deliverable.sign_status = DeliverableSignStatus.DRAFT

        summary = dict(version.signature_summary_json or {})
        signatures = list(summary.get("signatures", []))
        signatures.append(
            {
                "step_order": step.get("step_order", step_index),
                "step_role": sign_role,
                "decision": decision,
                "actor_user_id": str(actor_user_id),
                "actor_role": actor_role,
                "at": now.isoformat(),
            }
        )
        summary["signatures"] = signatures
        version.signature_summary_json = summary

        # 观测写入点 ①（ADR-0047 §① 🔒：service 层，非 API 层）
        await record_step(
            session=db,
            project_id=deliverable.project_id,
            workflow_type=WorkflowType.SIGN,
            workflow_id=version_id,
            step_order=int(step.get("step_order", step_index)),
            step_role=sign_role,
            state=state,
            actor_user_id=actor_user_id,
        )
        if next_step is not None and decision != "RETURN":
            await record_step(
                session=db,
                project_id=deliverable.project_id,
                workflow_type=WorkflowType.SIGN,
                workflow_id=version_id,
                step_order=int(next_step.get("step_order", step_index + 1)),
                step_role=str(next_step.get("sign_role", "")),
                state=WorkflowProgressState.IN_PROGRESS,
                actor_user_id=actor_user_id,
            )

        await AuditService(db).write(
            action=AuditAction.DELIVERABLE_SIGNED,
            resource_type="deliverable_version",
            resource_id=version_id,
            user_id=actor_user_id,
            detail={
                "step_order": step.get("step_order", step_index),
                "step_role": sign_role,
                "decision": decision,
            },
        )

        # ⚠️ 通知行与业务变更**同一个事务**（ADR §① 同步写裁决承诺的
        # 「同一次提交、同一套事务边界」）。推送在提交**之后**做 ——
        # 提交前推送 ⇒ commit 失败时用户收到一条会被回滚的通知（phantom）。
        pending = await cls._notify_sign_outcome(
            db,
            deliverable=deliverable,
            version=version,
            decision=decision,
            next_step=next_step,
            actor_user_id=actor_user_id,
        )
        await db.commit()
        await publish(pending)
        return SignStepOutcome(
            deliverable=deliverable,
            version=version,
            step_index=step_index,
            step_role=sign_role,
            decision=decision,
            state=state,
            signed_at=now,
        )

    @staticmethod
    async def _notify_sign_outcome(
        db: AsyncSession,
        *,
        deliverable: Deliverable,
        version: DeliverableVersion,
        decision: str,
        next_step: dict[str, Any] | None,
        actor_user_id: uuid.UUID,
    ) -> list[NotificationPayload]:
        """签署事件的通知触发（用户 2026-10-20 裁决的最小集合）。

        ⚠️ **只写不推、不提交**：本方法在业务变更的**同一个事务**里写通知行，
        由调用方一次提交，然后才推送。详见 `notify.notify` 的 docstring。
        """
        from app.models.notification import NotificationKind
        from app.services.notifications.notify import notify, notify_role
        from app.services.notifications.payload import NotificationDetail

        detail = NotificationDetail(
            project_id=deliverable.project_id,
            deliverable_id=deliverable.deliverable_id,
            deliverable_version_id=version.version_id,
            actor_id=actor_user_id,
            workflow_type="SIGN",
        )

        pending: list[NotificationPayload] = []
        if decision == "RETURN":
            # 退回的对象是「谁要返工」= 版本提交人，不是全体复核人。
            if version.created_by is not None:
                pending.append(
                    await notify(
                        db,
                        recipient_id=version.created_by,
                        kind=NotificationKind.STEP_RETURNED,
                        title=f"「{deliverable.title}」被退回",
                        body="请修改后重新签发",
                        detail=detail,
                    )
                )
        elif decision == "SIGN" and next_step is None:
            # ⚠️ **最后一步签完 ⇒ 交付物 APPROVED**。这一支原先完全没通知
            # 任何人 —— 而用户裁决的接线集合写的是「sign-step 成功」，
            # 字面包含最后一步。收件人 = 版本提交人（他等的就是这个结果），
            # 与代录完成的收件人口径一致。
            if version.created_by is not None:
                pending.append(
                    await notify(
                        db,
                        recipient_id=version.created_by,
                        kind=NotificationKind.SIGN_COMPLETED,
                        title=f"「{deliverable.title}」已批准",
                        body="签署流程已全部完成，交付物已批准",
                        detail=detail,
                    )
                )
        elif decision == "SIGN":
            pending = await notify_role(
                db,
                role=str(next_step.get("sign_role", "")),
                kind=NotificationKind.SIGN_COMPLETED,
                title=f"「{deliverable.title}」待你签署",
                body="有一份交付物在你的签署步骤上",
                detail=detail,
                project_id=deliverable.project_id,
                exclude_user_ids=(actor_user_id,),
            )
        return pending

    @staticmethod
    def _matrix_steps(matrix: SignatureMatrix | None) -> list[dict[str, Any]]:
        """取矩阵步骤，按 `step_order` 升序（**委托给唯一解析口**）。

        ⚠️ **不再自己解析 `steps_json`** —— 签署路径与变更单路径必须对同一份
        配置给出**同一组步骤**（RF-2）。解析规则集中在
        `SignatureMatrixService.parse_steps`：排序、坏项跳过、缺省补齐、
        全非法时报 422 `SIGNATURE_MATRIX_INVALID`。
        """
        return [
            {
                "step_order": s.step_order,
                "sign_role": s.sign_role,
                "required": s.required,
                "can_self_check": s.can_self_check,
                "can_skip": s.can_skip,
            }
            for s in SignatureMatrixService.parse_steps(matrix)
        ]

    @classmethod
    async def _assert_step_order(
        cls,
        db: AsyncSession,
        *,
        workflow_id: uuid.UUID,
        step: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> None:
        """步骤必须顺序推进；越步 ⇒ 409。

        「当前该签哪一步」由**已完成的观测行**决定，而不是由 `step_index` 自述 ——
        自述的序号可以被客户端随意填，拿它当真相等于没有顺序约束。
        """
        rows = (
            await db.execute(
                select(WorkflowProgress).where(
                    WorkflowProgress.workflow_id == workflow_id,
                    WorkflowProgress.workflow_type == WorkflowType.SIGN,
                )
            )
        ).scalars().all()
        done_orders = {
            r.step_order
            for r in rows
            if r.step_status
            in (
                WorkflowProgressState.COMPLETED,
                WorkflowProgressState.SKIPPED,
            )
        }
        expected: int | None = None
        for candidate in steps:
            if int(candidate.get("step_order", 0)) not in done_orders:
                expected = int(candidate.get("step_order", 0))
                break
        if expected is None:  # 全部步骤已终态
            expected = int(steps[-1].get("step_order", 0)) + 1

        if int(step.get("step_order", 0)) != expected:
            raise PcsError(
                code="SIGN_STEP_OUT_OF_ORDER",
                message=f"当前该签第 {expected} 步，收到第 {step.get('step_order')}",
                status=409,
            )

    # ------------------------------------------------------------------
    # 写面（P9A B3：代录客户批准 + 观测写入点 ③）
    # ------------------------------------------------------------------

    @classmethod
    async def record_customer_approval_proxy(
        cls,
        db: AsyncSession,
        *,
        deliverable_id: uuid.UUID,
        version_id: uuid.UUID,
        file_path: str,
        file_name: str,
        file_type: str,
        approver_name: str,
        approval_date: date,
        approval_method: str,
        secondary_username: str,
        secondary_password: str,
        actor_user_id: uuid.UUID,
    ) -> CustomerApprovalProxyOutcome:
        """代录客户批准（SPEC P9A-DLV-008 / ADR-0007）。

        客户在系统外批准（邮件/信函/EDMS/签字文件），由内部授权人把凭证代录进系统
        闭合 CUSTOMER 签署步骤 —— 客户不会有公司 AD 账号，这一步物理上无人能在
        系统内执行，代录是唯一的闭环。

        顺序上有两条不可交换的前置：

        1. **代录人不得是该交付物的设计人**（ADR-0007）。先查这条再查二次认证 ——
           设计人自录不该浪费一次 LDAP 往返，而且它给出的错误码更准。
        2. **代录人二次认证**（MFA 决议路径 B：AD 密码二次输入 + `SIGN_2FA_FALLBACK`）。

        凭证的 `file_hash` 由**服务端**从磁盘上的真实文件算 —— 请求里不收哈希，
        收了就是让客户端自证物证。

        Returns:
            `CustomerApprovalProxyOutcome`。

        Raises:
            PcsError 404 `DELIVERABLE_NOT_FOUND` / 404 `PROXY_VERSION_NOT_FOUND` /
                403 `PROXY_RECORDER_IS_DESIGNER` / 401 `SECONDARY_AUTH_FAILED` /
                400 `PROXY_ATTACHMENT_MISSING` / 400 `PROXY_ATTACHMENT_TOO_LARGE`
        """
        deliverable = await cls.get_or_404(db, deliverable_id=deliverable_id)
        version = await db.get(DeliverableVersion, version_id)
        if version is None or version.deliverable_id != deliverable_id:
            raise PcsError(
                code="PROXY_VERSION_NOT_FOUND",
                message=f"交付物 {deliverable_id} 下没有版本 {version_id}",
                status=404,
            )

        if version.created_by is not None and version.created_by == actor_user_id:
            raise PcsError(
                code="PROXY_RECORDER_IS_DESIGNER",
                message="ADR-0007：代录人不得是该交付物的设计人",
                status=403,
            )

        await verify_secondary_auth(
            session=db,
            username=secondary_username,
            password=secondary_password,
        )

        payload, file_hash = _read_credential(file_path)

        now = _utcnow()
        attachment = CustomerApprovalAttachment(
            deliverable_version_id=version_id,
            file_path=file_path,
            file_name=file_name,
            file_type=file_type,
            file_size=len(payload),
            uploaded_by=actor_user_id,
            file_hash=file_hash,
        )
        db.add(attachment)
        await db.flush()

        deliverable.customer_approval_date = approval_date
        deliverable.customer_approver_name = approver_name
        deliverable.customer_approval_method = approval_method
        deliverable.customer_approval_proxy_by = actor_user_id
        deliverable.customer_approval_proxy_at = now
        deliverable.customer_approval_attachment_id = attachment.attachment_id
        deliverable.customer_approval_is_proxy = True

        await AuditService(db).write(
            action=AuditAction.CUSTOMER_APPROVAL_PROXIED,
            resource_type="deliverable",
            resource_id=deliverable_id,
            user_id=actor_user_id,
            detail={
                "version_id": str(version_id),
                "attachment_id": str(attachment.attachment_id),
                "approver_name": approver_name,
                "approval_method": approval_method,
                "file_hash": file_hash,
            },
        )

        # 观测写入点 ③（ADR-0047 §① 🔒：service 层，非 API 层）
        await record_step(
            session=db,
            project_id=deliverable.project_id,
            workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY,
            workflow_id=deliverable_id,
            step_order=1,
            step_role="CUSTOMER",
            state=WorkflowProgressState.COMPLETED,
            actor_user_id=actor_user_id,
            result_hash=file_hash,
        )

        # ⚠️ 通知行与代录**同一个事务**；推送在提交之后（同 sign_step）。
        pending = await cls._notify_proxy_recorded(
            db, deliverable=deliverable, version=version
        )
        await db.commit()
        await db.refresh(attachment)
        await publish(pending)
        return CustomerApprovalProxyOutcome(
            deliverable=deliverable,
            version=version,
            attachment=attachment,
            signed_at=now,
        )

    @staticmethod
    async def _notify_proxy_recorded(
        db: AsyncSession,
        *,
        deliverable: Deliverable,
        version: DeliverableVersion,
    ) -> list[NotificationPayload]:
        """代录完成的通知触发（用户 2026-10-20 裁决的最小集合）。

        收件人 = 版本提交人。代录闭合的是**他**的交付物的 CUSTOMER 签署步骤，
        他是唯一因此状态发生变化的人。`created_by` 为空时不发也不报错 ——
        「没有明确收件人」是一种状态，不是一次失败。

        ⚠️ **只写不推、不提交**（同 `_notify_sign_outcome`）。
        """
        from app.models.notification import NotificationKind
        from app.services.notifications.notify import notify
        from app.services.notifications.payload import NotificationDetail

        if version.created_by is None:
            return []
        return [
            await notify(
                db,
                recipient_id=version.created_by,
                kind=NotificationKind.PROXY_RECORDED,
                title=f"「{deliverable.title}」客户批准已代录",
                body="客户批准凭证已登记，签署步骤已闭合",
                detail=NotificationDetail(
                    project_id=deliverable.project_id,
                    deliverable_id=deliverable.deliverable_id,
                    deliverable_version_id=version.version_id,
                    workflow_type="CUSTOMER_APPROVAL_PROXY",
                ),
            )
        ]

    # ------------------------------------------------------------------
    # 读面（P9A B4d：动作时间线）
    # ------------------------------------------------------------------

    @classmethod
    async def list_actions(
        cls,
        db: AsyncSession,
        *,
        deliverable_id: uuid.UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[Any], int]:
        """列交付物的动作时间线（数据源 = `audit_logs`，**不建新表**）。

        总纲「尚未解决」第 2 条到此关闭。理由：动作已经逐条写进审计了，
        再建一张表就是**第二份动作历史** —— 两份会漂移，而漂移的那份没人会去对。

        Returns:
            (`DeliverableActionRow` 列表, 总数)。
        """
        await cls.get_or_404(db, deliverable_id=deliverable_id)

        version_ids = (
            await db.execute(
                select(DeliverableVersion.version_id).where(
                    DeliverableVersion.deliverable_id == deliverable_id
                )
            )
        ).scalars().all()

        conditions = [
            and_(
                func.lower(AuditLog.resource_type) == "deliverable",
                AuditLog.resource_id == str(deliverable_id),
            )
        ]
        if version_ids:
            # 有版本才加第二个分支 —— 没有版本时 `IN ()` 在 PG 里是语法错误，
            # 塞个空串占位则是「永远不匹配」的哑条件，读代码的人要停下来想一遍
            # 才敢确认它无害。
            conditions.append(
                and_(
                    func.lower(AuditLog.resource_type) == "deliverable_version",
                    AuditLog.resource_id.in_([str(v) for v in version_ids]),
                )
            )
        total = await db.scalar(
            select(func.count()).select_from(AuditLog).where(or_(*conditions))
        )
        rows = (
            await db.execute(
                select(AuditLog)
                .where(or_(*conditions))
                # occurred_at 秒级粒度 ⇒ 必须带 audit_id 兜底，否则同一秒内的
                # 多条动作返回顺序不确定，翻页会漏或重（同本文件读面）。
                .order_by(AuditLog.occurred_at, AuditLog.audit_id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        from app.schemas.deliverable import DeliverableActionRow

        items = [
            DeliverableActionRow(
                action=r.action,
                resource_type=r.resource_type or "",
                resource_id=r.resource_id or "",
                actor_user_id=r.user_id,
                detail=r.detail_json,
                created_at=r.occurred_at,
            )
            for r in rows
        ]
        return items, int(total or 0)
