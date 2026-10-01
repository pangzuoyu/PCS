"""P7 Sprint 2 T4: auxiliary_consumption 4 字段 ALTER (util_results).

依据：

- P7-OPEN-009 §1 迁移范围 #6 + §3 工时表 (0.3 天)
- P7 SPEC V1.4 §3.2.2(5) + §4.6 + P7-OPEN-009 验收基准
- P7-OPEN-009 §1: electrical_power / fuel_gas_consumption /
  steam_consumption / cooling_water_consumption 4 字段

设计要点：

- ALTER TABLE util_results ADD COLUMN 4 数值字段（聚合 T1/T2/T3 子表
  annual_consumption + cooling_water 子表待立）+ 4 CHECK 约束 (非负)。
- 字段 nullable=True 起步（backward compat：Sprint 1 存量数据无值）；
  service 层 fallback 到 consumption_json JSONB 取值 (D1 裁决 1A)。
- 不引入 DEFAULT 0（避免 silent 误用：旧数据聚合前 N/A 显式 NULL）。
- 不加索引（聚合读多写少；非搜索列）。
- 不引入新枚举 / 外键（4 字段是纯度量，无 LEFT 字段）。

DOWN-REVISION = ``p7_open_009_003_utility_heat_exchange``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_004_auxiliary_consumption_4fields"
down_revision = "p7_open_009_003_utility_heat_exchange"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """ALTER util_results 表 ADD 4 字段 (auxiliary_consumption).

    字段定义严格对齐 app/models/util.py:UtilResults ORM class 新增 4 字段。
    """
    op.add_column(
        "util_results",
        sa.Column(
            "electrical_power_kwh_yr",
            sa.Float(),
            nullable=True,
            comment="年用电量 (kWh/yr; 聚合 utility_power_items.annual_consumption_kwh)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "fuel_gas_consumption_nm3_yr",
            sa.Float(),
            nullable=True,
            comment="年燃料气消耗量 (Nm³/yr; 聚合 utility_fuel_gas.annual_consumption_nm3)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "steam_consumption_t_yr",
            sa.Float(),
            nullable=True,
            comment="年蒸汽消耗量 (t/yr; 聚合 utility_heat_exchange.annual_consumption_t)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "cooling_water_consumption_t_yr",
            sa.Float(),
            nullable=True,
            comment="年冷却水消耗量 (t/yr; 待 P7-6B 冷却水子表落地后聚合)",
        ),
    )
    op.create_check_constraint(
        "ck_util_results_electrical_power_non_negative",
        "util_results",
        "electrical_power_kwh_yr IS NULL OR electrical_power_kwh_yr >= 0",
    )
    op.create_check_constraint(
        "ck_util_results_fuel_gas_non_negative",
        "util_results",
        "fuel_gas_consumption_nm3_yr IS NULL OR fuel_gas_consumption_nm3_yr >= 0",
    )
    op.create_check_constraint(
        "ck_util_results_steam_non_negative",
        "util_results",
        "steam_consumption_t_yr IS NULL OR steam_consumption_t_yr >= 0",
    )
    op.create_check_constraint(
        "ck_util_results_cooling_water_non_negative",
        "util_results",
        (
            "cooling_water_consumption_t_yr IS NULL "
            "OR cooling_water_consumption_t_yr >= 0"
        ),
    )


def downgrade() -> None:
    """DROP 4 auxiliary_consumption 字段 (T4 测试 / 回滚用)."""
    op.drop_constraint(
        "ck_util_results_cooling_water_non_negative", "util_results"
    )
    op.drop_constraint("ck_util_results_steam_non_negative", "util_results")
    op.drop_constraint("ck_util_results_fuel_gas_non_negative", "util_results")
    op.drop_constraint(
        "ck_util_results_electrical_power_non_negative", "util_results"
    )
    op.drop_column("util_results", "cooling_water_consumption_t_yr")
    op.drop_column("util_results", "steam_consumption_t_yr")
    op.drop_column("util_results", "fuel_gas_consumption_nm3_yr")
    op.drop_column("util_results", "electrical_power_kwh_yr")