"""SUP Sprint SYM-1: stream_symbols + project_stream_symbols 两表（V1.4 §7.1/§7.2）。

公司级符号表：symbol_id UUID PK + asset_id FK→config_assets（V1.4 §0.5/§INT-OPEN-01
asset_subtype=STREAM_SYMBOL）+ symbol str10 UNIQUE + 5 态 status。

项目级符号表：project_symbol_id UUID PK + source_symbol_id FK 可空（V1.4 §0.5
项目级 fork）+ symbol str10 + snapshot_json + override_json + 5 态 +
UNIQUE(project_id, symbol)。

TimestampMixin 三列由 ORM 层声明（created_at/updated_at/created_by）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_sym1_stream_symbols"
down_revision: str | None = "p2_sup_sprint_pc5_import_previews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """stream_symbols 主表创建（SYM-1 / SUP-002 §8 公司流股符号）。

    步骤：
    - 主表 stream_symbols：symbol_id (PK UUID) + asset_id (FK→config_assets) +
      symbol (unique 10 字符) + name + category + is_active (default true) +
      status (default 'DRAFT'，走 ConfigStateMachine 5 态机) + version +
      created_by + created_at + updated_at
    - 索引：symbol unique + status（按 5 态过滤）+ is_active（仅 active）
    - 配套：project_stream_symbols（项目级 fork 派生表，含 override_json）

    业务：公司级流股符号 5 态机；PUBLISHED 后 fork_project_symbols 复制到项目作用域
    生成 ProjectStreamSymbol（含 source_symbol_id 反向引用）。
    """
    op.create_table(
        "stream_symbols",
        sa.Column("symbol_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_foreign_key(
        "fk_stream_symbols_asset_id_config_assets",
        "stream_symbols", "config_assets",
        ["asset_id"], ["asset_id"],
    )
    op.create_index("ix_stream_symbols_status", "stream_symbols", ["status"])

    op.create_table(
        "project_stream_symbols",
        sa.Column("project_symbol_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("source_symbol_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("override_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "symbol", name="uq_project_stream_symbol"),
    )
    op.create_foreign_key(
        "fk_project_stream_symbols_project_id_projects",
        "project_stream_symbols", "projects",
        ["project_id"], ["project_id"],
    )
    op.create_foreign_key(
        "fk_project_stream_symbols_source_symbol_id_stream_symbols",
        "project_stream_symbols", "stream_symbols",
        ["source_symbol_id"], ["symbol_id"],
    )


def downgrade() -> None:
    op.drop_table("project_stream_symbols")
    op.drop_index("ix_stream_symbols_status", "stream_symbols")
    op.drop_table("stream_symbols")