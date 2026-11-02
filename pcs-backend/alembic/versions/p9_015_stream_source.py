"""给 `streams` 加 `source` 列（SPEC §7.7.1「来源」· P9B-3 · T2.5 · 用户裁决 1a）.

## 为什么

SPEC §7.7.1 的物流列表有「来源」列（SIM导入 / 手动 / Excel / 化验）——
后端此前**没有**承载它的字段（`data_mode` 是「数据模式」CHEMICAL/PETROLEUM/SOLID，
**不是**来源）⇒ 前端要么画一列假的，要么不画。

## ⚠️ 与既有 `streams.source_type` 的关系（别混）

- `source`（本列）= **录入通道**（怎么进系统的），4 值
- `source_type`（既有）= **产出方式**（数据怎么算出来的），13 值
  （3 人工/导入 + 10 个 `*_CALCULATED` 设备计算出口流）

两列正交；Excel 行上 `source='EXCEL'` 而 `source_type='SIM_IMPORT'` 是**有意的**
（`source_type` 词表里没有 EXCEL，本批不扩它）⇒ 已登记为未解决问题。

## 列形状（与 ORM `Stream.source` 一致）

`VARCHAR(20) / NOT NULL / DEFAULT 'MANUAL'`：存量行默认 MANUAL
（存量都是早期建的，无录入通道信息 ⇒ 默认「手动」是最诚实的近似）。

⚠️ 改迁移 ⇒ 必须验「迁移与 ORM 一致」（每库各一次，独立进程 + 直查库）。

## Revision

`revision = p9_015`，`down_revision = p9_014`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p9_015"
down_revision = "p9_014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加列 + CHECK + 复合索引."""
    op.add_column(
        "streams",
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
    )
    op.create_check_constraint(
        "ck_streams_source_valid",
        "streams",
        "source IN ('MANUAL','SIM_IMPORT','EXCEL','LAB')",
    )
    op.create_index(
        "ix_streams_project_source",
        "streams",
        ["project_id", "source"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """反向三个操作（索引 → 约束 → 列）."""
    op.drop_index("ix_streams_project_source", table_name="streams", if_exists=True)
    op.drop_constraint("ck_streams_source_valid", "streams", type_="check")
    op.drop_column("streams", "source")
