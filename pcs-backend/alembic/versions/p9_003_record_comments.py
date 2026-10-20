"""P9A 交付物写面：record_comments 表（批注）。

⚠️ **本迁移是 B4 开工时才发现要有的**：SPEC §2.2.3 列了
`POST /records/{module}/{id}/comments`，但全仓没有批注表。
计划只列了 B0 一个迁移 —— 不建表就只能返回「假批注」
（响应成功、刷新即消失），那比没有这个端点更坏：用户以为意见记下来了。

批注**不写** `workflow_progress`（ADR-0047 §①：观测层记的是流程进度，
「有人留言」不是流程活动）。

`(record_type, record_id)` 是组合键而非外键：记录是多态的（16+ 张结果表），
没有一张能当父表。本仓既有形状（`deliverable_record_bindings` /
`record_change_snapshots`）都是这么做的。代价是没有外键保护，
由读端点先解析记录（不存在 → 404）兜住。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p9_003"
down_revision = "p9_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "record_comments",
        # ⚠️ 与 ORM 声明逐字一致（app/models/record_comment.py）——
        # 不一致时 `alembic check` 报漂移，而漂移是**绿灯看不见**的那一类
        # （CLAUDE.md 漂移盲区：缺表会红，漂移会绿）。
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=30), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        # TimestampMixin 三列
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("comment_id"),
    )
    op.create_index(
        "ix_record_comments_project_id",
        "record_comments",
        ["project_id"],
        if_not_exists=True,
    )
    # 读路径索引。comment_id 作 tiebreaker：created_at 秒级粒度，
    # 同一批写入的批注时间戳相同，只按它排序时并列行顺序不确定 ⇒ 翻页会漏或重。
    op.create_index(
        "ix_record_comments_record_created",
        "record_comments",
        ["record_type", "record_id", "created_at", "comment_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_record_comments_record_created",
        table_name="record_comments",
        if_exists=True,
    )
    op.drop_index(
        "ix_record_comments_project_id", table_name="record_comments", if_exists=True
    )
    op.drop_table("record_comments", if_exists=True)
