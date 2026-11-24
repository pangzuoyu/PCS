"""p10_005：给 `report_definitions` 加「被退回」三列（P10-J · T2 · TODO-197b）。

## 为什么

「待我审核」队列（P10-I · T1）只有「发布 / 忽略」两个动作
⇒ ⇒ ⇒ 审核者看到**不合格**的草稿 ⇒ ⇒ **没有「打回」的路**
⇒ ⇒ ⇒ 产品上需要「拒绝」。

2026-11-24 人裁（四问全定）：
① 状态模型 = **退回 DRAFT + 一个「被退回」标记** ⇒ ⇒ ⇒ **不新增 `REJECTED` 态**
⇒ ⇒ ⇒ 9 态机**一个字不改**
② 谁可见 = **沿用现状 `visible_clause`** ⇒ ⇒ ⇒ 可见性规则不改
③ 能不能再编辑 = **能**（创建人改完再交审）
④ 要不要通知 = **要**

## ⚠️ **为什么是三个列而不是一个新状态**

「待审」（DRAFT 且没被打回）与「待改」（DRAFT 且被打回）是**两个态**
⇒ ⇒ ⇒ 队列只装前者（`pending_review()` 里 `rejected_at IS NULL`）
⇒ ⇒ ⇒ **不需要新状态** ⇒ ⇒ ⇒ 可见性 / 执行资格 / 列表过滤 / 前端 badge
**全都不用改**（badge 是**新增**的一列信号，不是新状态 ⇒ ⇒ ⇒ 状态色不变）。

## 列形状（与 ORM `ReportDefinition` 逐列一致）

| 列 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `rejected_at` | `TIMESTAMPTZ` | ✔ | 被打回的时刻（NULL = 没被打回）|
| `rejected_by` | `UUID` | ✔ | 谁打的回（**无 FK** —— 与 `executed_by` 同款：不留悬挂引用）|
| `reject_reason` | `TEXT` | ✔ | 原因（创建人看得见 ⇒ ⇒ ⇒ 填给人话）|

⚠️ **可空** ⇒ ⇒ 「没被打回」= 三列全 NULL ⇒ ⇒ ⇒ **不需要额外的布尔列**
⇒ ⇒ ⇒ 也不需要 `CHECK` 约束（三列各自可空就是判据）。

⚠️ **`rejected_by` 无 FK**：打回人离职 ⇒ ⇒ ⇒ FK 会让那条定义**永远删不掉**
⇒ ⇒ ⇒ 与 `report_execution_logs.executed_by` / `report_files` 的既有口径一致。

⚠️ 改迁移 ⇒ 必须验「迁移与 ORM 一致」（**每库各一次**，独立进程 + 直查库）
⇒ ⇒ ⇒ 单测跑的是 `metadata.create_all`（**从 ORM 建表**）⇒ ⇒ ⇒ 迁移漂移它抓不到。

## Revision

`revision = p10_005`，`down_revision = p10_004`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p10_005"
down_revision = "p10_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加三列（**全可空** ⇒ ⇒ 存量行不需要回填）。"""
    op.add_column(
        "report_definitions",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_definitions",
        sa.Column("rejected_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "report_definitions",
        sa.Column("reject_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """反向三列（**先删后加的逆序** ⇒ ⇒ 顺序也要一致）。"""
    op.drop_column("report_definitions", "reject_reason")
    op.drop_column("report_definitions", "rejected_by")
    op.drop_column("report_definitions", "rejected_at")
