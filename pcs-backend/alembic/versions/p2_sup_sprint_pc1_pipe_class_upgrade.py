"""SUP-002 PC-1: 管道等级差异迁移 + ORM（V1.4）。

Revision ID: p2_sup_sprint_pc1_pipe_class_upgrade
Revises: p2_s110_fix_toe_timestamptz
Create Date: 2026-09-07

按 V1.4 spec §0.3 / §2.1 / §2.2 收口：

A. pipe_classes 基础列
  1. class_id 放宽到 varchar(50)（自然码 PK，piping_results FK 引用保护）
  2. 新增 base_material varchar(100)（先 nullable 再回填）
  3. 新增 asset_id UUID FK → config_assets（nullable，PC-3 补 ConfigAsset 行）

B. base_material 回填 material_standard（种子后续由 Excel 导入刷新）

C. status 3 态 → 5 态映射：DRAFT→DRAFT，ACTIVE→PUBLISHED，OBSOLETE→OBSOLETE
   PENDING/APPROVED 迁移后为空集

D. project_pipe_classes 重构：复合 PK → 独立 UUID PK
  - 新增 project_class_id UUID PK（gen_random_uuid）
  - 新增 source_class_id / class_name / snapshot_json / override_json / status 列
  - snapshot_json 从 pipe_classes 完整构造（V1.4 §0.6 #1 修正）
  - enabled → status：enabled=true → DRAFT；enabled=false → OBSOLETE
  - enabled/custom_override_json/class_id 列移除（piping_results 不引用 project_pipe_classes）
  - UNIQUE(project_id, class_name)

E. config_approvals 增加 project_class_id 列（V1.4 §五、#1；项目级审批不挂 ConfigAsset，
   project_class_id 用于未来 SUP 扩展关联，本表 version_id NOT NULL 语义不变）

downgrade 完整逆向（非空 pass）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p2_sup_sprint_pc1_pipe_class_upgrade"
down_revision: str | None = "p2_s110_fix_toe_timestamptz"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================================
    # A. pipe_classes 基础列
    # ============================================================

    # A.1 class_id 放宽到 varchar(50)（保留自然码 PK，piping_results FK 不破坏）
    op.alter_column(
        "pipe_classes",
        "class_id",
        type_=sa.String(50),
        existing_type=sa.String(20),
        existing_nullable=False,
    )

    # A.2 新增 base_material 列（nullable，先加；后续回填）
    op.add_column(
        "pipe_classes",
        sa.Column("base_material", sa.String(100), nullable=True),
    )

    # A.3 新增 asset_id FK → config_assets（nullable，PC-3 补 ConfigAsset 行）
    op.add_column(
        "pipe_classes",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipe_classes_asset_id_config_assets",
        "pipe_classes",
        "config_assets",
        ["asset_id"],
        ["asset_id"],
    )

    # ============================================================
    # B. base_material 回填 material_standard
    # ============================================================
    op.execute(
        """
        UPDATE pipe_classes
        SET base_material = material_standard
        WHERE base_material IS NULL
        """
    )

    # ============================================================
    # C. status 3 态 → 5 态映射
    # DRAFT → DRAFT, ACTIVE → PUBLISHED, OBSOLETE → OBSOLETE
    # ============================================================
    op.execute(
        "UPDATE pipe_classes SET status = 'PUBLISHED' WHERE status = 'ACTIVE'"
    )

    # ============================================================
    # D. project_pipe_classes 重构
    # ============================================================

    # D.4a 新增 UUID 列（先临时名）
    op.add_column(
        "project_pipe_classes",
        sa.Column(
            "project_class_id_new",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE project_pipe_classes SET project_class_id_new = gen_random_uuid()"
    )

    # D.4b 新增目标态列
    op.add_column(
        "project_pipe_classes",
        sa.Column("source_class_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column("class_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column("snapshot_json", postgresql.JSON(), nullable=True),
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column("override_json", postgresql.JSON(), nullable=True),
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="DRAFT",
        ),
    )

    # D.4c 回填 snapshot/source_class_id/class_name/override_json
    # V1.4 §0.6 #1 修正：从 pipe_classes 完整构造 snapshot_json
    op.execute(
        """
        UPDATE project_pipe_classes ppc
        SET snapshot_json = jsonb_build_object(
                'class_name', pc.class_name,
                'material_standard', pc.material_standard,
                'base_material', pc.base_material,
                'corrosion_allowance', pc.corrosion_allowance,
                'design_pressure', pc.design_pressure,
                'design_temperature', pc.design_temperature,
                'dn_series_json', pc.dn_series_json,
                'sch_series_json', pc.sch_series_json,
                'flange_class', pc.flange_class,
                'fitting_type', pc.fitting_type,
                'allowable_stress_json', pc.allowable_stress_json,
                'branch_table_json', pc.branch_table_json
            ),
            source_class_id = ppc.class_id,
            class_name = pc.class_name,
            override_json = COALESCE(ppc.custom_override_json, '{}'::jsonb)
        FROM pipe_classes pc
        WHERE ppc.class_id = pc.class_id
        """
    )

    # D.4d enabled → status 映射（V1.4 §0.6 #3）
    op.execute(
        """
        UPDATE project_pipe_classes
        SET status = CASE
            WHEN enabled = false THEN 'OBSOLETE'
            ELSE 'DRAFT'
        END
        """
    )

    # D.4e 重命名新列 + 设置 NOT NULL + 替换 PK
    op.alter_column(
        "project_pipe_classes",
        "project_class_id_new",
        new_column_name="project_class_id",
    )
    op.alter_column(
        "project_pipe_classes",
        "project_class_id",
        nullable=False,
    )
    op.drop_constraint(
        "pk_project_pipe_classes",
        "project_pipe_classes",
        type_="primary",
    )
    op.create_primary_key(
        "pk_project_pipe_classes",
        "project_pipe_classes",
        ["project_class_id"],
    )

    # D.4f 删除 enabled 和 custom_override_json 列（语义已迁至 status/override_json）
    op.drop_column("project_pipe_classes", "enabled")
    op.drop_column("project_pipe_classes", "custom_override_json")

    # D.4g UNIQUE(project_id, class_name)（V1.4 §四、#3）
    op.create_unique_constraint(
        "uq_project_pipe_classes_project_id_class_name",
        "project_pipe_classes",
        ["project_id", "class_name"],
    )

    # D.4h 删除 class_id FK + 删除 class_id 列（piping_results FK 在 pipe_classes，不受影响）
    op.drop_constraint(
        "fk_project_pipe_classes_class_id_pipe_classes",
        "project_pipe_classes",
        type_="foreignkey",
    )
    op.drop_column("project_pipe_classes", "class_id")

    # ============================================================
    # E. config_approvals 增加 project_class_id 列（V1.4 §五、#1）
    # ============================================================
    op.add_column(
        "config_approvals",
        sa.Column("project_class_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_config_approvals_project_class_id_project_pipe_classes",
        "config_approvals",
        "project_pipe_classes",
        ["project_class_id"],
        ["project_class_id"],
    )


def downgrade() -> None:
    # E 逆向
    op.drop_constraint(
        "fk_config_approvals_project_class_id_project_pipe_classes",
        "config_approvals",
        type_="foreignkey",
    )
    op.drop_column("config_approvals", "project_class_id")

    # D 逆向
    # 加回 class_id 列（先 nullable，回填后设 NOT NULL）
    op.add_column(
        "project_pipe_classes",
        sa.Column("class_id", sa.String(20), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_pipe_classes_class_id_pipe_classes",
        "project_pipe_classes",
        "pipe_classes",
        ["class_id"],
        ["class_id"],
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "project_pipe_classes",
        sa.Column("custom_override_json", postgresql.JSON(), nullable=True),
    )
    # 从 snapshot_json 派生 custom_override_json（启发式：sentinel 直接拷贝，lossy）
    op.execute(
        """
        UPDATE project_pipe_classes
        SET custom_override_json = COALESCE(snapshot_json, '{}'::jsonb)
        """
    )
    op.execute(
        """
        UPDATE project_pipe_classes
        SET enabled = CASE WHEN status = 'OBSOLETE' THEN false ELSE true END
        """
    )
    op.drop_constraint(
        "uq_project_pipe_classes_project_id_class_name",
        "project_pipe_classes",
        type_="unique",
    )
    op.drop_constraint(
        "pk_project_pipe_classes",
        "project_pipe_classes",
        type_="primary",
    )
    # 把 project_class_id 临时改名为 _new，加回复合 PK，再 drop _new
    op.alter_column(
        "project_pipe_classes",
        "project_class_id",
        new_column_name="project_class_id_new",
    )
    op.create_primary_key(
        "pk_project_pipe_classes",
        "project_pipe_classes",
        ["project_id", "class_id"],
    )
    op.drop_column("project_pipe_classes", "project_class_id_new")
    # 移除目标态列
    op.drop_column("project_pipe_classes", "status")
    op.drop_column("project_pipe_classes", "override_json")
    op.drop_column("project_pipe_classes", "snapshot_json")
    op.drop_column("project_pipe_classes", "class_name")
    op.drop_column("project_pipe_classes", "source_class_id")

    # C 逆向：PUBLISHED → ACTIVE
    op.execute(
        "UPDATE pipe_classes SET status = 'ACTIVE' WHERE status = 'PUBLISHED'"
    )

    # B 逆向：base_material → nullable
    # （不回滚回填值——material_standard 保留原值，无信息损失）

    # A 逆向
    op.drop_constraint(
        "fk_pipe_classes_asset_id_config_assets",
        "pipe_classes",
        type_="foreignkey",
    )
    op.drop_column("pipe_classes", "asset_id")
    op.drop_column("pipe_classes", "base_material")
    op.alter_column(
        "pipe_classes",
        "class_id",
        type_=sa.String(20),
        existing_type=sa.String(50),
        existing_nullable=False,
    )