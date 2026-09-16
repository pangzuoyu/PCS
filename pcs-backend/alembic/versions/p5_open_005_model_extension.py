"""P5-0-1: 设备结果表扩展 + 双阶段设计下沉（SUP-008 §8.3.2/§8.3.3/§8.3.5 + §8.4 OPEN-009）。

P5-OPEN-005（V1.3）：3 张设备结果表 + design_stage 下沉：

1. **relief_results**（SUP-008 §8.3.2，P5 PSV 泄放量计算）
   - 13 业务字段：relief_scenario(6 态枚举，合并 P5-OPEN-005 含 UPSET) /
     source_equipment_id（多态：reactor/vessel/heat_exchanger） /
     reactor_volume/diameter/height / gas_tight_pressure / safety_factor /
     relief_rate_tier_1/2/3 / required_relief_area / selected_psv_id（FK psv_results）
   - 全套 RecordMixin 27 列

2. **column_sizing**（SUP-008 §8.3.3，P5 COLUMN 塔径核算）
   - 12 业务字段：column_tag / column_name / hysys_flooding_percent /
     hysys_calc_diameter_mm / selected_diameter_mm / reference_diameter_mm /
     tray_spacing_mm / tray_count / theoretical_tray_count / overall_efficiency /
     calc_date
   - **design_stage** 列下沉（§8.4 OPEN-009 VESSEL/PSV/COLUMN 三表）
   - 全套 RecordMixin 27 列

3. **mixer_results**（SUP-008 §8.3.5，P5 MIXER 压降）
   - 9 业务字段：mixer_tag / mixer_name / component_1_name/flow /
     component_2_name/flow / pressure_drop_kpa / check_result
   - 全套 RecordMixin 27 列

新增 PG enum：relief_scenario_enum（6 态）。
复用：design_stage_enum（P4-0-2 SUP-008 §8.4 已创建）+ recordsignstatus（P3.2 SIM-13）。

DOWN-REVISION = p4_task0_lineage_extension（P5-0 batch 最新基线）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p5_open_005_model_extension"
down_revision = "p4_task0_lineage_extension"
branch_labels = None
depends_on = None


# --- 1 个新 PG enum：relief_scenario_enum（6 态，P5-OPEN-005 合并版） ---
relief_scenario_enum = postgresql.ENUM(
    "FIRE",
    "CLOSED_VALVE",
    "REACTION_LOSS_OF_CONTROL",
    "BLOCKED_OUTLET",
    "COOLING_FAILURE",
    "UPSET",
    name="relief_scenario_enum",
    create_type=False,
)
# 复用既有 enum
design_stage_enum = postgresql.ENUM(
    "BASIC", "DETAIL", name="design_stage_enum", create_type=False
)
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


# RecordMixin 27 列（统一声明，避免三表重复 27 次）
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
    # 1. 创建 relief_scenario_enum（6 态）
    relief_scenario_enum.create(op.get_bind(), checkfirst=True)

    # 2. CREATE TABLE relief_results（13 业务 + 27 RecordMixin + project/workspace）
    op.create_table(
        "relief_results",
        sa.Column(
            "relief_id", sa.Uuid(), primary_key=True, nullable=False
        ),
        sa.Column(
            "source_equipment_id",
            sa.Uuid(),
            nullable=False,
            comment="源设备（多态 FK：reactor/vessel/heat_exchanger）",
        ),
        sa.Column("relief_scenario", relief_scenario_enum, nullable=False),
        sa.Column("reactor_volume", sa.Float(), nullable=True, comment="m³"),
        sa.Column("reactor_diameter", sa.Float(), nullable=True, comment="m"),
        sa.Column("reactor_height", sa.Float(), nullable=True, comment="m"),
        sa.Column("gas_tight_pressure", sa.Float(), nullable=True, comment="Bar"),
        sa.Column(
            "safety_factor",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.2"),
        ),
        sa.Column(
            "relief_rate_tier_1",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.7"),
            comment="MPa/min",
        ),
        sa.Column(
            "relief_rate_tier_2",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.4"),
            comment="MPa/min",
        ),
        sa.Column(
            "relief_rate_tier_3",
            sa.Float(),
            nullable=False,
            server_default=sa.text("2.1"),
            comment="MPa/min",
        ),
        sa.Column(
            "required_relief_area",
            sa.Float(),
            nullable=True,
            comment="cm²（API 521 公式输出）",
        ),
        sa.Column(
            "selected_psv_id",
            sa.Uuid(),
            sa.ForeignKey("psv_results.psv_id"),
            nullable=True,
            comment="选型 PSV（反查 psv_results）",
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
    )
    op.create_index(
        "ix_relief_results_project_id", "relief_results", ["project_id"]
    )
    op.create_index(
        "ix_relief_results_source_equipment_id",
        "relief_results",
        ["source_equipment_id"],
    )
    op.create_index(
        "ix_relief_results_workspace_id", "relief_results", ["workspace_id"]
    )

    # 3. CREATE TABLE column_sizing（12 业务 + design_stage + 27 RecordMixin + project/workspace）
    op.create_table(
        "column_sizing",
        sa.Column(
            "column_id", sa.Uuid(), primary_key=True, nullable=False
        ),
        sa.Column("column_tag", sa.String(length=50), nullable=False),
        sa.Column("column_name", sa.String(length=200), nullable=True),
        sa.Column(
            "hysys_flooding_percent", sa.Float(), nullable=True, comment="%"
        ),
        sa.Column(
            "hysys_calc_diameter_mm", sa.Float(), nullable=True, comment="mm"
        ),
        sa.Column(
            "selected_diameter_mm", sa.Float(), nullable=True, comment="mm"
        ),
        sa.Column(
            "reference_diameter_mm", sa.Float(), nullable=True, comment="mm"
        ),
        sa.Column("tray_spacing_mm", sa.Float(), nullable=True, comment="mm"),
        sa.Column("tray_count", sa.Integer(), nullable=True),
        sa.Column("theoretical_tray_count", sa.Integer(), nullable=True),
        sa.Column("overall_efficiency", sa.Float(), nullable=True, comment="%"),
        sa.Column("calc_date", sa.DateTime(), nullable=True, comment="计算日期"),
        sa.Column(
            "design_stage",
            design_stage_enum,
            nullable=False,
            server_default=sa.text("'BASIC'::design_stage_enum"),
            comment="§8.4 OPEN-009 VESSEL/PSV/COLUMN 三表下沉",
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
        sa.UniqueConstraint("project_id", "column_tag", name="uq_column_sizing_tag"),
    )
    op.create_index(
        "ix_column_sizing_project_id", "column_sizing", ["project_id"]
    )
    op.create_index(
        "ix_column_sizing_workspace_id", "column_sizing", ["workspace_id"]
    )

    # 4. CREATE TABLE mixer_results（9 业务 + 27 RecordMixin + project/workspace）
    op.create_table(
        "mixer_results",
        sa.Column(
            "mixer_id", sa.Uuid(), primary_key=True, nullable=False
        ),
        sa.Column("mixer_tag", sa.String(length=50), nullable=False),
        sa.Column("mixer_name", sa.String(length=200), nullable=True),
        sa.Column("component_1_name", sa.String(length=100), nullable=True),
        sa.Column("component_1_flow", sa.Float(), nullable=True, comment="m³/h"),
        sa.Column("component_2_name", sa.String(length=100), nullable=True),
        sa.Column("component_2_flow", sa.Float(), nullable=True, comment="m³/h"),
        sa.Column("pressure_drop_kpa", sa.Float(), nullable=True, comment="kPa"),
        sa.Column(
            "check_result", sa.String(length=20), nullable=True, comment="PASS/WARNING/FAIL"
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
        sa.UniqueConstraint("project_id", "mixer_tag", name="uq_mixer_results_tag"),
    )
    op.create_index(
        "ix_mixer_results_project_id", "mixer_results", ["project_id"]
    )
    op.create_index(
        "ix_mixer_results_workspace_id", "mixer_results", ["workspace_id"]
    )


def downgrade() -> None:
    # 顺序与 upgrade 相反：drop tables → drop enum
    op.drop_index("ix_mixer_results_workspace_id", table_name="mixer_results")
    op.drop_index("ix_mixer_results_project_id", table_name="mixer_results")
    op.drop_table("mixer_results")

    op.drop_index("ix_column_sizing_workspace_id", table_name="column_sizing")
    op.drop_index("ix_column_sizing_project_id", table_name="column_sizing")
    op.drop_table("column_sizing")

    op.drop_index("ix_relief_results_workspace_id", table_name="relief_results")
    op.drop_index("ix_relief_results_source_equipment_id", table_name="relief_results")
    op.drop_index("ix_relief_results_project_id", table_name="relief_results")
    op.drop_table("relief_results")

    op.execute("DROP TYPE IF EXISTS relief_scenario_enum")
