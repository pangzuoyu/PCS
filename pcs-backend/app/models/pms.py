"""PMS 管道材料规格（PMS = Pipe Material Specification）· P10-H · T2 · TODO-195。

## 为什么现在才有这张表

前端 P45-3-8 Task 35 画了「PMS 管道材料规格」页（`/pms`）⇒ ⇒ 但**后端
从来没有这个实体** ⇒ ⇒ 那一页只能占位（TODO-159 / TODO-195）。

## 口径（人裁 · 2026-11-23）

「沿用前端形状 + 签署流」⇒ ⇒ 字段 = 前端那一套
（`pms_no` / 描述 / `pms_class` / `hazard_level`）+ **9 态签署**。

⇒ ⇒ 继承 `RecordMixin` ⇒ ⇒ 直接吃仓内既有的**通用记录工作流**
（`/records/{module}/{record_id}/submit-approval` 等）⇒ ⇒ **不另造签署框架**
⇒ ⇒ 也不必再登记一份「谁有资格签」的清单。

`RECORD_TYPE_REGISTRY` 注册键 = `"PmsItem"`。
"""
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import RecordMixin


class PmsItem(RecordMixin, Base):
    """PMS 管道材料规格条目（pms_items 表）。

    业务：项目级的**管道材料规格**（SPEC §7.5「PMS / BEDD」章节）。
    ⚠️ SPEC §7.5 **没有给 PMS 的字段** ⇒ ⇒ 字段沿用前端 P45-3-8 的形状
    （人裁 2026-11-23）⇒ ⇒ 这里**照抄**，不另造。

    签署：`RecordMixin.sign_status`（9 态）⇒ ⇒ 送审 / 审批 / 作废都走
    通用记录工作流（module = `"PmsItem"`）。
    """

    __tablename__ = "pms_items"

    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    pms_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="PMS 编号（项目内唯一）",
    )
    description: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", comment="描述"
    )
    pms_class: Mapped[str] = mapped_column(
        String(40), nullable=False, default="", comment="材料等级 / 类别"
    )
    hazard_level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="LOW",
        comment="危险等级 LOW / MEDIUM / HIGH（驱动审批层级）",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "pms_no", name="uq_pms_items_project_pms_no"
        ),
        CheckConstraint(
            "hazard_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_pms_items_hazard_level",
        ),
        Index("ix_pms_items_created_at", "created_at"),
    )
