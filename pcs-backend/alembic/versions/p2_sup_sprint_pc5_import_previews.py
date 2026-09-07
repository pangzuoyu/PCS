"""SUP Sprint PC-5: pipe_class_import_previews 表（V1.4 §0.6/§三、#6）。

import_id 暂存选 DB 表方案（.wolf/cerebrum 未决问题 #3 已选）：服务端 preview 后
返 import_id，前端确认时携带 import_id，服务端按 import_id 取预览结果重放。包含
原文件 bytes + 解析结果 JSON + actor + expires_at。TTL 24h 后清理（service 层
按 expires_at 过滤过期）。consumed_at 首次 commit_import 写入，二次同 import_id
拒绝（防重复消费）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_pc5_import_previews"
down_revision: str | None = "p2_sup_sprint_pc4_config_approval_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipe_class_import_previews",
        sa.Column("import_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("parsed_json", sa.JSON(), nullable=False,
                  comment="ImportPreview 序列化：valid/errors/warnings"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="首次 commit_import 写入；二次同 import_id 拒绝"),
    )
    op.create_index(
        "ix_pc_import_previews_expires_at",
        "pipe_class_import_previews",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pc_import_previews_expires_at", "pipe_class_import_previews")
    op.drop_table("pipe_class_import_previews")
