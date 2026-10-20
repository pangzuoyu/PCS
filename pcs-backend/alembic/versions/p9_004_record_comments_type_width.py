"""record_comments.record_type 宽度 30 → 50。

原宽度 30 装不下 `RECORD_TYPE_REGISTRY` 里最长的键：
`ProjectCalculationStandardProfile` 是 33 字符。给这类记录留言时
Postgres 会在**入库那一刻**拒绝，报的是 500 而不是 422 ——
用户看到的是「系统错误」，而真正该说的话是「这条记录的批注失败了」。

50 与 `audit_logs.resource_type` 同宽：两处存的是同一份词表的键，
宽度不一致只会在跨表比对时变成一条查不出来的记录。

⚠️ `String` 加宽是 PG 上的表重写；本表是 P9A 同批新建的（p9_003 刚落），
实际数据量为 0，重写成本可忽略。已发布的迁移不改写，故另起一条。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p9_004"
down_revision = "p9_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "record_comments",
        "record_type",
        type_=sa.String(length=50),
        existing_type=sa.String(length=30),
        existing_nullable=False,
    )


def downgrade() -> None:
    # ⚠️ 收窄回 30 可能**失败**：若已有超过 30 字符的键入库，收窄会被 PG 拒绝。
    # 这不是 bug，是收窄本身的语义 —— 数据已经证明 30 不够。
    op.alter_column(
        "record_comments",
        "record_type",
        type_=sa.String(length=30),
        existing_type=sa.String(length=50),
        existing_nullable=False,
    )
