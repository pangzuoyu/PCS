"""P7 Sprint 2 T2: utility_fuel_gas 表 (燃料气).

依据：

- P7-OPEN-009 §1 迁移范围 #2 + §3 工时表 (0.5 天)
- P7 SPEC V1.4 §3.2.2(5) + §4.6 + P7-OPEN-009 验收基准
- P7-OPEN-009 §1: calorific_value / consumption / annual_consumption
  3 字段 + 初期/末期/最大工况 枚举

设计要点：

- 单张 utility_fuel_gas 表存燃料气 (natural gas / refinery gas / LPG 等)
  消耗量。
- 3 业务字段：calorific_value_kcal_nm3 / consumption_nm3_h /
  annual_consumption_nm3 + operating_phase enum (INITIAL/STEADY/MAX,
  初期/末期/最大工况) + 3 CHECK 约束 (数值范围)。
- FK equipment_id → equipment_list.equipment_id (nullable: PMS 早期
  数据可能未关联)。
- UNIQUE(project_id, equipment_tag, operating_phase) 防重复录入
  (每设备每工况 1 行)。
- 不继承 TaggedRecordMixin (公用工程记录，非业务计算 tagged 记录)。

DOWN-REVISION = ``p7_open_009_001_utility_power_items``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_002_utility_fuel_gas"
down_revision = "p7_open_009_001_utility_power_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 utility_fuel_gas 表 (P7 Sprint 2 T2 / P7-OPEN-009 §1 #2).

    字段定义严格对齐 app/models/util.py:UtilityFuelGas ORM class.
    """
    op.create_table(
        "utility_fuel_gas",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            comment="UUID 主键 (uuid.uuid4 default)",
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
            comment="项目 ID (FK projects.project_id)",
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
            nullable=False,
            comment="工作区 ID (FK workspaces.workspace_id)",
        ),
        sa.Column(
            "equipment_id",
            sa.Uuid(),
            sa.ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"),
            nullable=True,
            comment="设备 ID (FK equipment_list.equipment_id; nullable: PMS 早期数据可能未关联)",
        ),
        sa.Column(
            "equipment_tag",
            sa.String(length=64),
            nullable=False,
            comment="设备位号 (项目内唯一, 与 operating_phase 联合 UNIQUE)",
        ),
        sa.Column(
            "fuel_type",
            sa.String(length=32),
            nullable=False,
            server_default="NATURAL_GAS",
            comment="燃料类型: NATURAL_GAS / REFINERY_GAS / LPG / LNG / OTHERS",
        ),
        sa.Column(
            "calorific_value_kcal_nm3",
            sa.Float(),
            nullable=False,
            comment="低位热值 (kcal/Nm³; 典型天然气 8000~9000)",
        ),
        sa.Column(
            "consumption_nm3_h",
            sa.Float(),
            nullable=False,
            comment="小时消耗量 (Nm³/h)",
        ),
        sa.Column(
            "operating_phase",
            sa.String(length=16),
            nullable=False,
            comment="操作工况: INITIAL (初期) / STEADY (末期/稳态) / MAX (最大工况)",
        ),
        sa.Column(
            "operating_hours_per_year",
            sa.Float(),
            nullable=False,
            server_default="8000",
            comment="该工况年运行小时数 (h/yr; ≤ 8760)",
        ),
        sa.Column(
            "annual_consumption_nm3",
            sa.Float(),
            nullable=False,
            comment="年消耗量 (Nm³/yr; = consumption_nm3_h × operating_hours_per_year)",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="MANUAL",
            comment="数据来源: PMS (设备管理系统) / MANUAL (手动录入) / CALC (计算)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="记录创建时间 (DB server_default)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="记录更新时间 (ORM onupdate 触发)",
        ),
        sa.CheckConstraint(
            "calorific_value_kcal_nm3 > 0 AND calorific_value_kcal_nm3 <= 20000",
            name="ck_utility_fuel_gas_calorific_value_range",
        ),
        sa.CheckConstraint(
            "consumption_nm3_h > 0",
            name="ck_utility_fuel_gas_consumption_positive",
        ),
        sa.CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_fuel_gas_hours_in_year",
        ),
        sa.CheckConstraint(
            "annual_consumption_nm3 >= 0",
            name="ck_utility_fuel_gas_annual_consumption_non_negative",
        ),
        sa.CheckConstraint(
            "operating_phase IN ('INITIAL', 'STEADY', 'MAX')",
            name="ck_utility_fuel_gas_operating_phase_enum",
        ),
        sa.UniqueConstraint(
            "project_id", "equipment_tag", "operating_phase",
            name="uq_utility_fuel_gas_project_equipment_phase",
        ),
    )
    op.create_index(
        "ix_utility_fuel_gas_project",
        "utility_fuel_gas",
        ["project_id"],
    )
    op.create_index(
        "ix_utility_fuel_gas_workspace",
        "utility_fuel_gas",
        ["workspace_id"],
    )
    op.create_index(
        "ix_utility_fuel_gas_fuel_type",
        "utility_fuel_gas",
        ["fuel_type"],
    )


def downgrade() -> None:
    """删除 utility_fuel_gas 表 (T2 测试 / 回滚用)."""
    op.drop_index("ix_utility_fuel_gas_fuel_type", table_name="utility_fuel_gas")
    op.drop_index("ix_utility_fuel_gas_workspace", table_name="utility_fuel_gas")
    op.drop_index("ix_utility_fuel_gas_project", table_name="utility_fuel_gas")
    op.drop_table("utility_fuel_gas")