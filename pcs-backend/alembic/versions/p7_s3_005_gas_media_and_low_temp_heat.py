"""p7_s3_005: utility_gas_media + utility_low_temp_heat (P7-6B 收尾).

补上 T5 长期缺失的 2 个子表。`_aggregate_util_subtables` 里的
`gas_nm3_yr` / `low_temp_heat_gj_yr` 此前是**硬编码 None**, 而 CONFIG 里

    NITROGEN          0.15  kg标油/m³   (附录A 序号33)
    INSTRUMENT_AIR    0.038 / 0.028     (序号31 净化 / 序号32 非净化)
    GAS               0.85
    LOW_TEMP_HEAT     0.012 kg标油/MJ   (序号34)

的系数一直存在却从无代码读取 —— 死数据。氮气与仪表空气从未进过综合能耗。

Revision ID: p7_s3_005
Revises: p7_s3_004
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_005"
down_revision = "p7_s3_004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    """建 utility_gas_media (Nm³) + utility_low_temp_heat (GJ) 两张子表."""
    op.create_table(
        "utility_gas_media",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id", sa.Uuid(), sa.ForeignKey("projects.project_id",
                                                   ondelete="CASCADE"),
            nullable=False, comment="项目 ID (FK projects.project_id)",
        ),
        sa.Column(
            "workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.workspace_id",
                                                     ondelete="RESTRICT"),
            nullable=False, comment="工作区 ID (FK workspaces.workspace_id)",
        ),
        sa.Column(
            "equipment_id", sa.Uuid(),
            sa.ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"),
            nullable=True, comment="设备 ID (FK equipment_list.equipment_id)",
        ),
        sa.Column("equipment_tag", sa.String(64), nullable=False,
                  comment="设备位号 (与 gas_medium 联合 UNIQUE)"),
        sa.Column(
            "gas_medium", sa.String(32), nullable=False,
            comment=(
                "气体介质 (GasMedium): PROCESS_GAS / NITROGEN / PURIFIED_AIR / "
                "NON_PURIFIED_AIR / PLANT_AIR"
            ),
        ),
        sa.Column("consumption_nm3_h", sa.Float(), nullable=False,
                  comment="小时消耗量 (Nm³/h)"),
        sa.Column("operating_hours_per_year", sa.Float(), nullable=False,
                  server_default="8000", comment="年运行小时数 (h/yr; ≤ 8760)"),
        sa.Column(
            "annual_consumption_nm3", sa.Float(), nullable=False,
            comment="年消耗量 (Nm³/yr; = consumption_nm3_h × operating_hours_per_year)",
        ),
        sa.Column("source", sa.String(32), nullable=False,
                  server_default="MANUAL",
                  comment="数据来源: PMS / MANUAL / CALC"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "project_id", "equipment_tag", "gas_medium",
            name="uq_utility_gas_media_project_equipment_medium",
        ),
        sa.CheckConstraint(
            "gas_medium IN ('PROCESS_GAS', 'NITROGEN', 'PURIFIED_AIR', "
            "'NON_PURIFIED_AIR', 'PLANT_AIR')",
            name="ck_utility_gas_media_medium",
        ),
        sa.CheckConstraint(
            "consumption_nm3_h >= 0 AND annual_consumption_nm3 >= 0",
            name="ck_utility_gas_media_nonneg",
        ),
    )
    op.create_index("ix_utility_gas_media_project", "utility_gas_media",
                    ["project_id"], if_not_exists=True)
    op.create_index("ix_utility_gas_media_workspace", "utility_gas_media",
                    ["workspace_id"], if_not_exists=True)
    op.create_index("ix_utility_gas_media_gas_medium", "utility_gas_media",
                    ["gas_medium"], if_not_exists=True)

    op.create_table(
        "utility_low_temp_heat",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id", sa.Uuid(), sa.ForeignKey("projects.project_id",
                                                   ondelete="CASCADE"),
            nullable=False, comment="项目 ID (FK projects.project_id)",
        ),
        sa.Column(
            "workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.workspace_id",
                                                     ondelete="RESTRICT"),
            nullable=False, comment="工作区 ID (FK workspaces.workspace_id)",
        ),
        sa.Column(
            "equipment_id", sa.Uuid(),
            sa.ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"),
            nullable=True, comment="设备 ID (FK equipment_list.equipment_id)",
        ),
        sa.Column("equipment_tag", sa.String(64), nullable=False,
                  comment="设备位号 (项目内唯一)"),
        sa.Column("heat_recovery_gj_h", sa.Float(), nullable=False,
                  comment="小时回收热量 (GJ/h)"),
        sa.Column("operating_hours_per_year", sa.Float(), nullable=False,
                  server_default="8000", comment="年运行小时数 (h/yr; ≤ 8760)"),
        sa.Column(
            "annual_recovered_heat_gj", sa.Float(), nullable=False,
            comment=(
                "年回收热量 (GJ/yr)。折标: GJ×1000→MJ × 0.012 kg标油/MJ "
                "(GB 30251-2024 附录A 序号34)"
            ),
        ),
        sa.Column("source", sa.String(32), nullable=False,
                  server_default="MANUAL",
                  comment="数据来源: PMS / MANUAL / CALC"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_low_temp_heat_project_equipment",
        ),
        sa.CheckConstraint(
            "heat_recovery_gj_h >= 0 AND annual_recovered_heat_gj >= 0",
            name="ck_utility_low_temp_heat_nonneg",
        ),
    )
    op.create_index("ix_utility_low_temp_heat_project", "utility_low_temp_heat",
                    ["project_id"], if_not_exists=True)
    op.create_index("ix_utility_low_temp_heat_workspace", "utility_low_temp_heat",
                    ["workspace_id"], if_not_exists=True)


def downgrade() -> None:
    """删两张子表 (if_exists 幂等)."""
    op.drop_table("utility_low_temp_heat", if_exists=True)
    op.drop_table("utility_gas_media", if_exists=True)
