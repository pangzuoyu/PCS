"""P9A C0：notifications 表 + 部分索引（ADR-0049 §①/§③）。

SPEC P9A-NOT-001（通知建表）/ ADR-0049 §①（通知是发生过的事实，不可实时计算）
/ §③（部分索引是 500ms 指标的全部支撑）。

## revision 号为何是 p9_005 而不是计划写的 p9_003

计划 C0 的文件名写的是 `p9_003_notifications.py`，但 `p9_003` 已被
B lane 的 `p9_003_record_comments.py` 占用（revision id 不可重名）。
沿用 B lane 之后的下一个号 `p9_005`，`down_revision = "p9_004"`。

## 无 project_id

通知的读路径是「当前用户读自己的」，鉴权身份就是 `recipient_id` 本身。
加 `project_id` 会制造第二个可写错、且写错后鉴权仍通过的依据。

## kind 是 String(40) 不是 PG enum

若 DB 侧再开一份 kind 清单，「Python 有哪些」与「DB 允许哪些」就是两份
必须同步维护的清单（TODO-058 同类问题）。DB 放宽，Python 的
`NotificationKind` 是唯一来源。

## 部分索引必须在本迁移里

ADR-0049 §③ 明写「该索引必须进迁移」。建成全量索引时已读行也进索引，
未读占比一降索引就失去选择性 —— 而这种缺失不会让任何测试变红。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p9_005"
down_revision = "p9_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        # ⚠️ 与 ORM 声明逐字一致（app/models/notification.py）——
        # 不一致时 `alembic check` 报漂移，而漂移是**绿灯看不见**的那一类
        # （CLAUDE.md 漂移盲区：缺表会红，漂移会绿）。
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("detail_json", postgresql.JSONB(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        # TimestampMixin 三列（app/models/mixins.py:34-41）
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    # ⚠️ postgresql_where 不能省 —— 这是 ADR-0049 §③ 的硬要求。
    op.create_index(
        "ix_notifications_recipient_unread",
        "notifications",
        ["recipient_id", "read_at"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    # 断线兜底（ADR-0049 §⑤ 约束 1）：`GET /notifications?after=<last_seen>`
    # 按 created_at 范围翻页。
    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["recipient_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_recipient_created", table_name="notifications"
    )
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_table("notifications")
