"""P5-0-1b T1: thermosiphon_circulation_results 表（SUP-010 §3.5）.

热虹吸循环安装高度计算结果表。数据来源 132汽包安装高度计算(2014.6.12).xls
（6 sheet：卧式 E-106 / E-206 / E-207 / 二中 4 张 + 立式 外取热器 / R-104 2 张），
见 SUP-010 §2.1.3 gap 分析与 §3.5 完整 DDL。

内容：
- 11 业务字段：equipment_tag / equipment_name / circulation_type /
  shell_diameter / drum_diameter / drum_liquid_level /
  installation_height_calc / installation_height_final / safety_factor /
  check_result / circulation_drive_ratio
- 4 JSONB 容器（SUP-010 §3.5 逐字命名）：inlet_pipe_params /
  outlet_pipe_params / shell_side_params / other_params
- UNIQUE(project_id, equipment_tag) —— SUP-010 §3.5 声明
- 7 CHECK 约束（工艺室 §5.2 数值范围）
- RecordMixin 全套 27 列 + project_id / workspace_id

DDL 列名保留 SUP-010 §3.5 逐字命名（不带单位后缀）；单位后缀只在
service / schema 层显式（工艺室 §5.2 要求，DDL 层不强制）。

复用：recordsignstatus（P3.2 SIM-13）—— 本表不新增 PG enum
（circulation_type / check_result 用 String + CHECK，避免为 2 值建 enum）。

DOWN-REVISION = p6_9_pickup_4_drift_fixes（P6-9-PICKUP-4 收口后当前 alembic HEAD）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p5_0_1b_1_thermosiphon"
down_revision = "p6_9_pickup_4_drift_fixes"
branch_labels = None
depends_on = None

# 复用既有 PG enum（create_type=False；本迁移不创建 enum）
recordsignstatus_enum = postgresql.ENUM(
    "DRAFT",
    "IN_APPROVAL",
    "CHECKED",
    "OBSOLETE",
    "CHECK_REJECTED",
    "STALE",
    "CHANGE_PENDING",
    "CHANGED",
    "REVERSAL_PENDING",
    name="recordsignstatus",
    create_type=False,
)

# RecordMixin 27 列（与 p5_open_005 逐字对齐，避免重复声明漂移）
_RECORD_MIXIN_COLUMNS = [
    sa.Column("tag_number", sa.String(length=50), nullable=True),
    sa.Column(
        "sign_status",
        recordsignstatus_enum,
        nullable=False,
        server_default=sa.text("'DRAFT'::recordsignstatus"),
    ),
    sa.Column("record_hash", sa.String(length=64), nullable=False, server_default=""),
    sa.Column("approval_step", sa.Integer(), nullable=True),
    sa.Column(
        "approval_depth", sa.Integer(), nullable=False, server_default=sa.text("1")
    ),
    sa.Column("approval_role", sa.String(length=30), nullable=True),
    sa.Column(
        "locked_by_deliverable",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column("created_by", sa.Uuid(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    # change_* 组（ADR-0002）
    sa.Column("change_pending_since", sa.DateTime(timezone=True), nullable=True),
    sa.Column("change_resolved_by", sa.String(length=64), nullable=True),
    sa.Column("change_resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("change_abandoned_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "change_abandoned_reason", sa.String(length=500), nullable=True
    ),
    # obsoleted_* 组（ADR-0009）
    sa.Column("obsoleted_reason", sa.String(length=200), nullable=True),
    sa.Column("obsoleted_by", sa.Uuid(), nullable=True),
    sa.Column("obsoleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "obsoleted_via_deliverable_id", sa.Uuid(), nullable=True
    ),
    # reversal_* 组（ADR-0010）
    sa.Column("reversal_requested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reversal_requested_by", sa.Uuid(), nullable=True),
    sa.Column("reversal_reason", sa.String(length=500), nullable=True),
    sa.Column("reversal_approved_by", sa.Uuid(), nullable=True),
    sa.Column("reversal_approved_at", sa.DateTime(timezone=True), nullable=True),
    # P4-0-1 审计列（ADR-0031）
    sa.Column("stale_resolution_path", sa.String(length=30), nullable=True),
    sa.Column(
        "hash_changed", sa.Boolean(), nullable=True, server_default=sa.text("false")
    ),
    sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
]


def upgrade() -> None:
    """创建 thermosiphon_circulation_results（11 业务 + 4 JSONB + 27 RecordMixin）."""
    op.create_table(
        "thermosiphon_circulation_results",
        # 主键
        sa.Column(
            "thermosiphon_id", sa.Uuid(), primary_key=True, nullable=False
        ),
        # 基本标识
        sa.Column(
            "equipment_tag",
            sa.String(length=50),
            nullable=False,
            comment="蒸汽发生器编号（如 E-106）",
        ),
        sa.Column("equipment_name", sa.String(length=200), nullable=True, comment="设备名称"),
        sa.Column(
            "circulation_type",
            sa.String(length=30),
            nullable=False,
            comment="循环类型：HORIZONTAL / VERTICAL",
        ),
        # 主要几何参数
        sa.Column("shell_diameter", sa.Float(), nullable=True, comment="壳体壳径 Ds（m）"),
        sa.Column("drum_diameter", sa.Float(), nullable=True, comment="汽包直径（m）"),
        sa.Column(
            "drum_liquid_level", sa.Float(), nullable=True, comment="汽包液位高 H1（m）"
        ),
        # 计算结果
        sa.Column(
            "installation_height_calc",
            sa.Float(),
            nullable=True,
            comment="计算安装高度 Hx（m）",
        ),
        sa.Column(
            "installation_height_final",
            sa.Float(),
            nullable=True,
            comment="最终安装高度 Hxo（取 1.5 倍余量，m）",
        ),
        sa.Column(
            "safety_factor",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.5"),
            comment="安全余量倍数（SUP-010 §3.5 default 1.5）",
        ),
        sa.Column(
            "check_result", sa.String(length=20), nullable=True, comment="校核 PASS / FAIL"
        ),
        sa.Column(
            "circulation_drive_ratio",
            sa.Float(),
            nullable=True,
            comment="（立式）循环推动力 / 总压力降之比",
        ),
        # 详细参数 JSONB（适应卧式 / 立式差异）
        sa.Column(
            "inlet_pipe_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="入口管线参数 {mass_flow_kg_per_h, density_kg_per_m3, "
            "velocity_m_per_s, inner_diam_m, equivalent_length_m, friction_factor, "
            "reynolds, pressure_drop_const, pressure_drop_coeff}",
        ),
        sa.Column(
            "outlet_pipe_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="出口管线参数（inlet 基础上增 vapor_fraction / mixture_density / "
            "mixture_viscosity）",
        ),
        sa.Column(
            "shell_side_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="壳程参数 {avg_density, static_head, friction_drop, flow_area, "
            "baffle_spacing, baffle_count}",
        ),
        sa.Column(
            "other_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="其他参数（立式特有 Martinelli Xtt / φ / 混合密度 / 沸腾区压降 / "
            "动能损失）",
        ),
        *_RECORD_MIXIN_COLUMNS,
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.project_id"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.workspace_id"),
            nullable=False,
        ),
        # SUP-010 §3.5 UNIQUE(project_id, equipment_tag)
        sa.UniqueConstraint(
            "project_id",
            "equipment_tag",
            name="uq_thermosiphon_circulation_results_tag",
        ),
        # 数值范围 CHECK（工艺室 §5.2）
        sa.CheckConstraint(
            "circulation_type IN ('HORIZONTAL', 'VERTICAL')",
            name="thermosiphon_circulation_type_chk",
        ),
        sa.CheckConstraint(
            "check_result IS NULL OR check_result IN ('PASS', 'FAIL')",
            name="thermosiphon_check_result_chk",
        ),
        sa.CheckConstraint("safety_factor > 0", name="thermosiphon_safety_factor_chk"),
        sa.CheckConstraint(
            "shell_diameter IS NULL OR shell_diameter > 0",
            name="thermosiphon_shell_diameter_chk",
        ),
        sa.CheckConstraint(
            "drum_diameter IS NULL OR drum_diameter > 0",
            name="thermosiphon_drum_diameter_chk",
        ),
        sa.CheckConstraint(
            "drum_liquid_level IS NULL OR drum_liquid_level >= 0",
            name="thermosiphon_drum_liquid_level_chk",
        ),
        sa.CheckConstraint(
            "circulation_drive_ratio IS NULL OR circulation_drive_ratio > 0",
            name="thermosiphon_drive_ratio_chk",
        ),
    )
    op.create_index(
        "ix_thermosiphon_circulation_results_project_id",
        "thermosiphon_circulation_results",
        ["project_id"],
    )
    op.create_index(
        "ix_thermosiphon_circulation_results_workspace_id",
        "thermosiphon_circulation_results",
        ["workspace_id"],
    )


def downgrade() -> None:
    """回退：drop 索引 → drop 表；本表不建 enum，无 enum 清理."""
    op.drop_index(
        "ix_thermosiphon_circulation_results_workspace_id",
        table_name="thermosiphon_circulation_results",
    )
    op.drop_index(
        "ix_thermosiphon_circulation_results_project_id",
        table_name="thermosiphon_circulation_results",
    )
    op.drop_table("thermosiphon_circulation_results")
