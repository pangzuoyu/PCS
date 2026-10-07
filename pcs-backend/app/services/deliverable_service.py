"""交付物读服务（P1-7+ D 模块 / P8 前置）。

P8 REPORT 的实际依赖是「从 `deliverables` / `deliverable_versions` 读数据」——
`docs/PCS-NOTE-P8前置清单与3项修订-2026-10-07.md` ② 列出该缺口时，确认现状是
**有 9 个模型、有 ChangeNoticeService，但无 service / schema / API**。

本服务只做读面。三个写端点（create / issue / customer-approval-proxy）服务的是
P9 签署流程，**刻意不在本轮实现** —— 见 TODOS.md。

## 为什么写服务没有一并做

P1 spec §3.2 的 5 个端点里，写的那三个都要过签署矩阵（SUP-005）、编号模板
（ADR-0006）、ADR-0007 的二次认证。这些是 P9 的范围，且当前缺一份能对齐的
矩阵消费方（`SignatureMatrix.steps_json` 无 service）。**先交 P8 真正需要的读面**，
把 P8 的路径打通，比五个端点各写一半可用要好。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.deliverable import (
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
)


class DeliverableService:
    """交付物读面。全部 classmethod，与 ChangeNoticeService 同风格。"""

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