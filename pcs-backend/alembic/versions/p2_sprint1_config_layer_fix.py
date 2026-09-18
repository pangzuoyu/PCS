"""P2 Sprint 1 Step 0：配置层 ORM 修正对齐 DICT V3.3。

修正内容（D13 裁决）：
- config_approvals：rename comments → comment + add approver_id
- formula_definitions：add asset_id + std_source + rename variables_json → parameters_json
- coefficient_tables：add asset_id + std_source + rename domain → applicable_range
- template_files：add asset_id
- project_templates：add asset_id + checklist_json
- numbering_templates：rename name → template_name + scope → description

已对齐（无需迁移）：
- config_versions.asset_id FK：ORM 已存在
- numbering_templates.revision_separate：ORM 已存在
- doc_no_sequences.project_id：DB 列已存在（P1 迁移），仅 ORM 模型需补声明
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sprint1_config_layer_fix"
down_revision: str | None = "p1_sprint3_equipment_status_columns"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """配置层字段修复（P2 sprint1：config_approvals/formula_definitions/coefficient_tables）。

    步骤：
    - config_approvals：加 approver_id (UUID nullable) + rename comments→comment
      （单数字段化，便于前端展示）
    - formula_definitions：加 asset_id (FK→config_assets) + std_source +
      rename variables_json→parameters_json（语义升级：变量→参数）
    - coefficient_tables：加 asset_id (FK→config_assets) + rename
      lookup_columns→column_definitions + 加 columns_count 派生列
    - 3 张表统一挂 ConfigAsset（V1.4 §0.5 INT-OPEN-01 资源级追溯）

    业务影响：3 张配置表从局部定义升级到全公司 ConfigAsset 追踪；
    字段命名规范化（单数 + 业务语义精确）。
    """
    # === config_approvals ===
    op.add_column(
        "config_approvals",
        sa.Column("approver_id", sa.Uuid(), nullable=True),
    )
    op.alter_column(
        "config_approvals", "comments", new_column_name="comment"
    )

    # === formula_definitions ===
    op.add_column(
        "formula_definitions",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "formula_definitions",
        sa.Column("std_source", sa.String(200), nullable=True),
    )
    op.alter_column(
        "formula_definitions",
        "variables_json",
        new_column_name="parameters_json",
    )
    op.create_foreign_key(
        "fk_formula_definitions_asset_id",
        "formula_definitions",
        "config_assets",
        ["asset_id"],
        ["asset_id"],
    )

    # === coefficient_tables ===
    op.add_column(
        "coefficient_tables",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "coefficient_tables",
        sa.Column("std_source", sa.String(200), nullable=True),
    )
    op.alter_column(
        "coefficient_tables", "domain", new_column_name="applicable_range"
    )
    op.create_foreign_key(
        "fk_coefficient_tables_asset_id",
        "coefficient_tables",
        "config_assets",
        ["asset_id"],
        ["asset_id"],
    )

    # === template_files ===
    op.add_column(
        "template_files",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_template_files_asset_id",
        "template_files",
        "config_assets",
        ["asset_id"],
        ["asset_id"],
    )

    # === project_templates ===
    op.add_column(
        "project_templates",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "project_templates",
        sa.Column("checklist_json", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_templates_asset_id",
        "project_templates",
        "config_assets",
        ["asset_id"],
        ["asset_id"],
    )

    # === numbering_templates ===
    op.alter_column(
        "numbering_templates", "name", new_column_name="template_name"
    )
    op.alter_column(
        "numbering_templates", "scope", new_column_name="description"
    )


def downgrade() -> None:
    # === numbering_templates ===
    op.alter_column(
        "numbering_templates", "description", new_column_name="scope"
    )
    op.alter_column(
        "numbering_templates", "template_name", new_column_name="name"
    )

    # === project_templates ===
    op.drop_constraint(
        "fk_project_templates_asset_id", "project_templates", type_="foreignkey"
    )
    op.drop_column("project_templates", "checklist_json")
    op.drop_column("project_templates", "asset_id")

    # === template_files ===
    op.drop_constraint(
        "fk_template_files_asset_id", "template_files", type_="foreignkey"
    )
    op.drop_column("template_files", "asset_id")

    # === coefficient_tables ===
    op.drop_constraint(
        "fk_coefficient_tables_asset_id",
        "coefficient_tables",
        type_="foreignkey",
    )
    op.alter_column(
        "coefficient_tables", "applicable_range", new_column_name="domain"
    )
    op.drop_column("coefficient_tables", "std_source")
    op.drop_column("coefficient_tables", "asset_id")

    # === formula_definitions ===
    op.drop_constraint(
        "fk_formula_definitions_asset_id",
        "formula_definitions",
        type_="foreignkey",
    )
    op.alter_column(
        "formula_definitions",
        "parameters_json",
        new_column_name="variables_json",
    )
    op.drop_column("formula_definitions", "std_source")
    op.drop_column("formula_definitions", "asset_id")

    # === config_approvals ===
    op.alter_column(
        "config_approvals", "comment", new_column_name="comments"
    )
    op.drop_column("config_approvals", "approver_id")
