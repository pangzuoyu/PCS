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
    """pipe_class_import_previews 主表创建（PC-5 / V1.4 §0.6/§三、#6）。

    步骤：
    - 主表 pipe_class_import_previews：import_id (PK UUID) + actor_id (FK→users)
    - 存原文件：file_bytes LargeBinary（完整保留供重新解析）
    - 解析结果：parsed_json JSON（ImportPreview 序列化：valid/errors/warnings）
    - 计数：error_count / warning_count INT default 0（前端概览统计）
    - 时间戳：created_at / expires_at（service 层按 expires_at 过滤 24h 过期清理）
    - consumed_at NULL（首次 commit_import 写入；二次同 import_id 拒绝，防重复消费）
    - 索引：ix_pc_import_previews_expires_at（过期清理加速）

    业务：import_id 暂存选 DB 表方案（cerebrum #3 已选）— 服务端 preview 后
    返 import_id，前端确认携带 import_id，服务端按 import_id 取预览重放。
    """
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
    """pipe_class_import_previews 表 + 索引删除（PC-5 落地逆向）。

    步骤：
    - DROP INDEX ix_pc_import_previews_expires_at
    - DROP TABLE pipe_class_import_previews

    业务：与 upgrade 互逆；管架导入预览批次表 + expires_at 索引清理。
    """
    op.drop_index("ix_pc_import_previews_expires_at", "pipe_class_import_previews")
    op.drop_table("pipe_class_import_previews")
