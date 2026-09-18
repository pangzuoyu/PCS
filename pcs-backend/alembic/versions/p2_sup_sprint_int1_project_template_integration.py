"""SUP Sprint INT-1: project_templates 增 pipe_code_template_id 列
+ project_template_pipe_classes 关联表（V1.4 §15）。

INT-DROP-01 撤销 stream_symbol_table_id 列（公司符号表无聚合实体）。
PC-OPEN-04 项目创建时自动 fork 默认等级 → 关联表记录模板级默认等级清单。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_int1_project_template_integration"
down_revision: str | None = "p2_sup_sprint_fmt1b_sequence_counter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """项目模板 × 管架/管号 集成（INT-1 + PC-OPEN-04，V1.4 §15）。

    步骤：
    - A. project_templates 加 pipe_code_template_id UUID NULL + FK→pipe_code_templates
    - B. 关联表 project_template_pipe_classes（template_id × class_id 复合 PK）：
      记录项目模板默认携带的管架清单
    - C. 双向 FK：template_id → project_templates / class_id → pipe_classes

    不做：撤销 stream_symbol_table_id 列（INT-DROP-01 公司符号表无聚合实体）。

    业务：项目创建时自动 fork 默认等级（PC-OPEN-04）→ 关联表记录模板级
    默认等级清单；project_templates.pipe_code_template_id 引导生成管号。
    """
    # 1. project_templates 增 pipe_code_template_id 列（nullable）
    op.add_column(
        "project_templates",
        sa.Column("pipe_code_template_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_templates_pct_id_pct",
        "project_templates",
        "pipe_code_templates",
        ["pipe_code_template_id"],
        ["template_id"],
    )

    # 2. 关联表 project_template_pipe_classes（PC-OPEN-04）
    op.create_table(
        "project_template_pipe_classes",
        sa.Column("template_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "template_id", "class_id", name="pk_project_template_pipe_classes",
        ),
    )
    op.create_foreign_key(
        "fk_ptpc_template_id_project_templates",
        "project_template_pipe_classes",
        "project_templates",
        ["template_id"],
        ["template_id"],
    )
    op.create_foreign_key(
        "fk_ptpc_class_id_pipe_classes",
        "project_template_pipe_classes",
        "pipe_classes",
        ["class_id"],
        ["class_id"],
    )


def downgrade() -> None:
    op.drop_table("project_template_pipe_classes")
    op.drop_constraint(
        "fk_project_templates_pct_id_pct",
        "project_templates",
        type_="foreignkey",
    )
    op.drop_column("project_templates", "pipe_code_template_id")