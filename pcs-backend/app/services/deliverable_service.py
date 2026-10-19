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

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.config_domain import NumberingTemplate
from app.models.deliverable import (
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
from app.models.workflow_progress import WorkflowProgress
from app.services.audit_service import AuditService
from app.services.numbering_service import NumberingService
from app.services.workflow_progress_writer import record_step

#: `segments_json` 里已登记的占位符（P2 计划设计 §3.5 的示例段名）。
#: 匹配「标识符形状」（小写 + 下划线）的段一律按占位符解析，
#: 解析不到 ⇒ 报错；其余（`-` / `/` 等）按字面量原样拼接。
_TOKEN_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
        if duplicated is not None:
            raise PcsError(
                code="DELIVERABLE_ALREADY_ISSUED",
                message=(
                    f"交付物 {deliverable_id} 已有版本目的 {version_purpose} 的版本"
                    f"（rev={duplicated.rev}）"
                ),
                status=409,
            )

        matrix = await db.get(SignatureMatrix, deliverable.matrix_id)
        doc_no = await cls._allocate_doc_no(db, deliverable=deliverable)
        rev = await cls._next_rev(db, deliverable_id=deliverable_id)

        version = DeliverableVersion(
            deliverable_id=deliverable_id,
            rev=rev,
            version_purpose=version_purpose,
            description=description or f"签发版本 rev={rev}（{version_purpose}）",
            # 记录绑定在 B4 的 submit-approval / 快照固化里补；签发时只有矩阵步骤。
            record_snapshot_json={"record_count": 0},
            signature_summary_json={
                "matrix_id": str(deliverable.matrix_id),
                "steps": (matrix.steps_json if matrix is not None else []),
            },
            created_by=actor_user_id,
        )
        db.add(version)

        deliverable.doc_no = doc_no
        deliverable.current_rev = rev
        deliverable.version_purpose = version_purpose
        deliverable.sign_status = DeliverableSignStatus.PENDING

        await AuditService(db).write(
            action=AuditAction.DELIVERABLE_ISSUED,
            resource_type="deliverable",
            resource_id=deliverable_id,
            user_id=actor_user_id,
            detail={
                "rev": rev,
                "version_purpose": version_purpose,
                "doc_no": doc_no,
            },
        )

        await db.commit()
        await db.refresh(version)
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
        elif decision == "RETURN":
            # 退回 = 交付物整体回草稿。后续要改内容必须重新 issue 出新版本，
            # 不能在原版本上继续推进 —— 否则退回的理由会挂在已签过的版本上。
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

        await db.commit()
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
    def _matrix_steps(matrix: SignatureMatrix | None) -> list[dict[str, Any]]:
        """取矩阵步骤，按 `step_order` 升序。

        `steps_json` 的键序不保证（它是一个 JSON 数组，写入方爱怎么排怎么排），
        而签署推进完全依赖顺序 ⇒ 必须显式排序，不能靠数组下标。
        矩阵缺失或步骤为空 ⇒ 空列表（调用方按越界处理）。
        """
        if matrix is None or not matrix.steps_json:
            return []
        steps = [s for s in matrix.steps_json if isinstance(s, dict)]
        return sorted(steps, key=lambda s: s.get("step_order", 0))

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
