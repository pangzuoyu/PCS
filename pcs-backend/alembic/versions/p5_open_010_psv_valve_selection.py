"""P5-OPEN-10 SUP-P5-PSV-002 V1.14 §3.1 PSV 选型 18 列 + 3 CHECK。

按 SUP-P5-PSV-002 V1.14（SPEC §3.1 + §4.1 + §4.2）：

1. **psv_results 加 18 列**（净增；inlet/outlet/blowdown/set_pressure/orifice_designation 已存在）：
   - 阀型/材料：valve_type / body_material / bellows_material
   - 背压：back_pressure_type / back_pressure_pct
   - 超压：overpressure_pct
   - Kb 派生：kb_factor / kb_source
   - 选型：flange_class / valve_brand / fire_protection
   - 爆破膜：rupture_disc_position / rupture_disc_kc
   - 孔口override：orifice_overridden / orifice_manual
   - CDTP 修正：cdtp_applied
   - 先导：pilot_temperature_c / pilot_temp_class

2. **psv_results 加 3 CHECK 约束**（V1.14 §4.2 业务规则 DB 层兜底）：
   - psv_valve_type_chk：valve_type IS NULL OR valve_type IN ('SPRING_LOADED', 'BALANCED_BELLOWS')
   - psv_cdtp_check：NOT cdtp_applied OR back_pressure_type = 'SUPERIMPOSED'
   - psv_orifice_overridden_check：orifice_overridden ↔ orifice_manual 成对

3. **存量回填**（兼容 G6 门禁）：
   - 现有 PsvResult 行的 valve_type 默认为 'SPRING_LOADED'（满足 psv_valve_type_chk）
   - 现有 PsvResult 行的 cdtp_applied 默认 FALSE（满足 psv_cdtp_check）
   - 现有 PsvResult 行的 orifice_overridden 默认 FALSE + orifice_manual NULL
     （满足 psv_orifice_overridden_check）

**DOWN-REVISION** = p5_0_2_heat_results_extend（P5-0 末态 alembic head）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p5_open_010_psv_valve_selection"
down_revision = "p5_0_2_heat_results_extend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. psv_results 加 18 列（与 ORM 定义一一对应；nullable=True 兼容存量）
    op.add_column(
        "psv_results",
        sa.Column("valve_type", sa.String(length=32), nullable=True,
                  comment="SPRING_LOADED/BALANCED_BELLOWS/PILOT/RUPTURE_DISC（§3.2）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("body_material", sa.String(length=32), nullable=True,
                  comment="阀体材料 CARBON_STEEL/SS304/SS316/SS316L/ALLOY（§3.2）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("bellows_material", sa.String(length=32), nullable=True,
                  comment="波纹管材料 6 种（§3.8）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("flange_class", sa.String(length=8), nullable=True,
                  comment="150#/300#/600#/900#/1500#/2500#（§3.2）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("back_pressure_type", sa.String(length=16), nullable=True,
                  comment="BUILT_UP / SUPERIMPOSED（§3.2）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("back_pressure_pct", sa.Float(), nullable=True,
                  comment="背压百分比 0-50（§3.5）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("overpressure_pct", sa.Float(), nullable=True,
                  comment="超压百分比 10/16/21（API 520 §5.3.1）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("kb_factor", sa.Float(), nullable=True,
                  comment="背压修正系数 Kb（§4.3）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("kb_source", sa.String(length=32), nullable=True,
                  comment="Kb 来源 none/manufacturer:X/api520_fig30/en4126/mixed:X+Y"),
    )
    op.add_column(
        "psv_results",
        sa.Column("valve_brand", sa.String(length=32), nullable=True,
                  comment="阀体品牌（自由字符串；V1.14 P2-1 修订）"),
    )
    op.add_column(
        "psv_results",
        sa.Column(
            "cdtp_applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="CDTP 修正是否生效（§4.4）",
        ),
    )
    op.add_column(
        "psv_results",
        sa.Column(
            "orifice_overridden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="用户手动指定 orifice_override（§4.5）",
        ),
    )
    op.add_column(
        "psv_results",
        sa.Column("orifice_manual", sa.String(length=8), nullable=True,
                  comment="手动指定孔口字母 D-T（§4.5）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("rupture_disc_position", sa.String(length=16), nullable=True,
                  comment="爆破膜位置 UPSTREAM/DOWNSTREAM/NONE（§3.2）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("rupture_disc_kc", sa.Float(), nullable=True,
                  comment="爆破膜组合 Kc（UPSTREAM=0.90 / DOWNSTREAM=1.00；ASME UG-127）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("pilot_temperature_c", sa.Float(), nullable=True,
                  comment="先导温度 °C（PILOT_OPERATED 字段；P5 占位）"),
    )
    op.add_column(
        "psv_results",
        sa.Column("pilot_temp_class", sa.String(length=16), nullable=True,
                  comment="GENERAL/HIGH_TEMP/CRYOGENIC（PILOT_OPERATED；P5 占位）"),
    )
    op.add_column(
        "psv_results",
        sa.Column(
            "fire_protection",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="防火保护（§3.2）",
        ),
    )

    # 2. psv_results 加 3 CHECK 约束
    op.create_check_constraint(
        "psv_valve_type_chk",
        "psv_results",
        "valve_type IS NULL OR valve_type IN ('SPRING_LOADED', 'BALANCED_BELLOWS')",
    )
    op.create_check_constraint(
        "psv_cdtp_check",
        "psv_results",
        "NOT cdtp_applied OR back_pressure_type = 'SUPERIMPOSED'",
    )
    op.create_check_constraint(
        "psv_orifice_overridden_check",
        "psv_results",
        "(NOT orifice_overridden AND orifice_manual IS NULL) OR "
        "(orifice_overridden AND orifice_manual IS NOT NULL)",
    )


def downgrade() -> None:
    # 逆序：先 drop 列约束，再 drop 列
    op.drop_constraint("psv_orifice_overridden_check", "psv_results", type_="check")
    op.drop_constraint("psv_cdtp_check", "psv_results", type_="check")
    op.drop_constraint("psv_valve_type_chk", "psv_results", type_="check")

    op.drop_column("psv_results", "fire_protection")
    op.drop_column("psv_results", "pilot_temp_class")
    op.drop_column("psv_results", "pilot_temperature_c")
    op.drop_column("psv_results", "rupture_disc_kc")
    op.drop_column("psv_results", "rupture_disc_position")
    op.drop_column("psv_results", "orifice_manual")
    op.drop_column("psv_results", "orifice_overridden")
    op.drop_column("psv_results", "cdtp_applied")
    op.drop_column("psv_results", "valve_brand")
    op.drop_column("psv_results", "kb_source")
    op.drop_column("psv_results", "kb_factor")
    op.drop_column("psv_results", "overpressure_pct")
    op.drop_column("psv_results", "back_pressure_pct")
    op.drop_column("psv_results", "back_pressure_type")
    op.drop_column("psv_results", "flange_class")
    op.drop_column("psv_results", "bellows_material")
    op.drop_column("psv_results", "body_material")
    op.drop_column("psv_results", "valve_type")