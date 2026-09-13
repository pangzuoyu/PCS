"""P4-0-2: SUP-008 OPEN-008 表扩展 + OPEN-009 design_stage。

SUP-008 V1.1 §8.3 / OPEN-008（管/泵/两相结果字段）+ OPEN-009（设计阶段 BASIC/DETAIL）：

- piping_results +11 列：
  line_description / pipe_type(enum) / max_flow_factor / selected_diameter /
  liquid_velocity_max / gas_velocity_max / pressure_drop_per_100m /
  selected_pipe_size / recommended_pipe_size / check_result(enum) /
  velocity_range_reference
- pump_results +5 列：
  selected_pump_model / selected_motor_model / selected_motor_power /
  pump_operation(enum) + design_stage(enum, NOT NULL default BASIC)
- psv_results / vessel_results +design_stage(enum, NOT NULL default BASIC)
- 新表 two_phase_results（13 字段 + TaggedRecordMixin 字段），SPEC §8.3.4：
  two_phase_calc_id(PK uuid) / input_json / output_json / Bx / By /
  flow_pattern(enum) / two_phase_check(enum) / liquid_velocity /
  gas_velocity / pressure_gradient / void_fraction / calc_method / created_at
- 6 个 PG enum：pipe_type_enum / check_result_enum / pump_operation_enum /
  design_stage_enum / flow_pattern_enum / two_phase_check_enum

down_revision = p4_calc_audit_fields
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p4_sup008_result_fields"
down_revision = "p4_calc_audit_fields"
branch_labels = None
depends_on = None


# --- 6 个 PG enum 集中声明 ---

pipe_type_enum = postgresql.ENUM(
    "PUMP_SUCTION",
    "PUMP_DISCHARGE",
    "SELF_FLOW",
    "HEATING_STEAM",
    "TWO_PHASE",
    name="pipe_type_enum",
    create_type=False,
)

check_result_enum = postgresql.ENUM(
    "PASS",
    "FAIL",
    "WARNING",
    name="check_result_enum",
    create_type=False,
)

pump_operation_enum = postgresql.ENUM(
    "NORMAL",
    "STANDBY",
    "OFF",
    name="pump_operation_enum",
    create_type=False,
)

design_stage_enum = postgresql.ENUM(
    "BASIC",
    "DETAIL",
    name="design_stage_enum",
    create_type=False,
)

flow_pattern_enum = postgresql.ENUM(
    "ANNULAR",
    "MIST",
    "BUBBLE",
    "SLUG",
    "STRATIFIED",
    "WAVE",
    name="flow_pattern_enum",
    create_type=False,
)

two_phase_check_enum = postgresql.ENUM(
    "PASS",
    "WARNING",
    "FAIL",
    name="two_phase_check_enum",
    create_type=False,
)


def upgrade() -> None:
    # 1. 创建 6 个 PG enum 类型
    postgresql.ENUM(
        "PUMP_SUCTION",
        "PUMP_DISCHARGE",
        "SELF_FLOW",
        "HEATING_STEAM",
        "TWO_PHASE",
        name="pipe_type_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "PASS",
        "FAIL",
        "WARNING",
        name="check_result_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "NORMAL",
        "STANDBY",
        "OFF",
        name="pump_operation_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "BASIC",
        "DETAIL",
        name="design_stage_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "ANNULAR",
        "MIST",
        "BUBBLE",
        "SLUG",
        "STRATIFIED",
        "WAVE",
        name="flow_pattern_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "PASS",
        "WARNING",
        "FAIL",
        name="two_phase_check_enum",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)

    # 2. piping_results +11 列
    op.add_column(
        "piping_results",
        sa.Column("line_description", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column("pipe_type", pipe_type_enum, nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column("max_flow_factor", sa.Float(), nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column("selected_diameter", sa.Float(), nullable=True, comment="mm"),
    )
    op.add_column(
        "piping_results",
        sa.Column("liquid_velocity_max", sa.Float(), nullable=True, comment="m/s"),
    )
    op.add_column(
        "piping_results",
        sa.Column("gas_velocity_max", sa.Float(), nullable=True, comment="m/s"),
    )
    op.add_column(
        "piping_results",
        sa.Column(
            "pressure_drop_per_100m",
            sa.Float(),
            nullable=True,
            comment="kPa/100m",
        ),
    )
    op.add_column(
        "piping_results",
        sa.Column("selected_pipe_size", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column("recommended_pipe_size", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column("check_result", check_result_enum, nullable=True),
    )
    op.add_column(
        "piping_results",
        sa.Column(
            "velocity_range_reference",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # 3. pump_results +4 列
    op.add_column(
        "pump_results",
        sa.Column("selected_pump_model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "pump_results",
        sa.Column("selected_motor_model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "pump_results",
        sa.Column(
            "selected_motor_power",
            sa.Float(),
            nullable=True,
            comment="kW",
        ),
    )
    op.add_column(
        "pump_results",
        sa.Column("pump_operation", pump_operation_enum, nullable=True),
    )

    # 4. design_stage 三表：pump_results / psv_results / vessel_results
    for table in ("pump_results", "psv_results", "vessel_results"):
        op.add_column(
            table,
            sa.Column(
                "design_stage",
                design_stage_enum,
                nullable=False,
                server_default=sa.text("'BASIC'::design_stage_enum"),
                comment="设计阶段 BASIC/DETAIL（OPEN-009）",
            ),
        )

    # 5. 新表 two_phase_results（13 列）
    # 不放 TaggedRecordMixin 字段（mixin 列由后续 P4-TASK0 / 批次自治管理）；
    # 这里保持与 brief 一致，仅落 brief 列出的 13 字段。
    op.create_table(
        "two_phase_results",
        sa.Column("two_phase_calc_id", sa.Uuid(), primary_key=True),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("Bx", sa.Float(), nullable=True, comment="Lockhart-Martinelli 参数"),
        sa.Column("By", sa.Float(), nullable=True, comment="Lockhart-Martinelli 参数"),
        sa.Column("flow_pattern", flow_pattern_enum, nullable=True),
        sa.Column("two_phase_check", two_phase_check_enum, nullable=True),
        sa.Column("liquid_velocity", sa.Float(), nullable=True, comment="m/s"),
        sa.Column("gas_velocity", sa.Float(), nullable=True, comment="m/s"),
        sa.Column(
            "pressure_gradient",
            sa.Float(),
            nullable=True,
            comment="kPa/m",
        ),
        sa.Column("void_fraction", sa.Float(), nullable=True),
        sa.Column("calc_method", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # 反向：先删表/列，再 drop enum
    op.drop_table("two_phase_results")

    for table in ("vessel_results", "psv_results", "pump_results"):
        op.drop_column(table, "design_stage")

    op.drop_column("pump_results", "pump_operation")
    op.drop_column("pump_results", "selected_motor_power")
    op.drop_column("pump_results", "selected_motor_model")
    op.drop_column("pump_results", "selected_pump_model")

    op.drop_column("piping_results", "velocity_range_reference")
    op.drop_column("piping_results", "check_result")
    op.drop_column("piping_results", "recommended_pipe_size")
    op.drop_column("piping_results", "selected_pipe_size")
    op.drop_column("piping_results", "pressure_drop_per_100m")
    op.drop_column("piping_results", "gas_velocity_max")
    op.drop_column("piping_results", "liquid_velocity_max")
    op.drop_column("piping_results", "selected_diameter")
    op.drop_column("piping_results", "max_flow_factor")
    op.drop_column("piping_results", "pipe_type")
    op.drop_column("piping_results", "line_description")

    # 6 个 enum：倒序 DROP（依赖解除顺序无关，但保持倒序便于排查）
    op.execute("DROP TYPE IF EXISTS two_phase_check_enum")
    op.execute("DROP TYPE IF EXISTS flow_pattern_enum")
    op.execute("DROP TYPE IF EXISTS design_stage_enum")
    op.execute("DROP TYPE IF EXISTS pump_operation_enum")
    op.execute("DROP TYPE IF EXISTS check_result_enum")
    op.execute("DROP TYPE IF EXISTS pipe_type_enum")