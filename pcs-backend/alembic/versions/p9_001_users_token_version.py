"""P9A 身份迁移：users.token_version + CHECK >= 1。

ADR-0046 §④（token_version 引入）、§③b（0 是 mock 令牌的哨兵 ⇒ 真实用户永不为 0）。

⚠️ 本迁移只做身份一件事 —— 其余三样分属 lane B/C/D：
`workflow_progress` 表（B）、`notifications` 表（C）、`cost_est_results.record_hash`（D）。
理由：仓库迁移惯例是 0~2 个 DDL，合并会让 4 条 lane 卡在同一个 alembic head 上。

users 表当前 0 行 ⇒ `server_default='1'` 直接覆盖存量，无需回填脚本。
"""
from alembic import op
import sqlalchemy as sa

revision = "p9_001"
down_revision = "p8_011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("'1'"),
            comment="吊销版本；0 为保留值（mock 令牌哨兵），真实用户永不为 0",
        ),
    )
    op.create_check_constraint(
        "ck_users_token_version_ge_1", "users", "token_version >= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_token_version_ge_1", "users", type_="check")
    op.drop_column("users", "token_version")
