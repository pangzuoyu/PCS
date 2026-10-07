"""P7 Sprint 2 R1 修订: PCS 数据模型调整 (F-P0-001 R1 §7)

Per PCS-SIGN-F-P0-001-2026-10-08-R1 §7:
- utility_heat_exchange.steam_pressure → 映射 9 档压力等级 (GE_7_0_MPA / 4_5_TO_7_0_MPA / ... / LT_0_3_MPA)
- utility_heat_exchange.medium_type → 映射 9 类水类型 (FRESH_WATER / CIRCULATING_WATER / ... / 120C_CONDENSATE_REUSABLE)
- utility_fuel_gas.fuel_type → 映射油田气/气田气/炼厂燃料气 (OILFIELD_GAS / GASFIELD_GAS / REFINERY_FUEL_GAS)
- 新增 electricity_value_type 字段 → 当量值/等价值 (EQUIVALENT / EQUIVALENT_VALUE)

R1 修订后 R0 单一值 (LP/MP/HP + NATURAL_GAS) 与 R1 9 档 + 3 类不兼容.
最小变更: 新增 4 字段 (nullable); 保留旧字段兼容 (deprecated 注释). 后续 sprint 用数据回填脚本迁移.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "p7_open_010_r1_classification_fields"
down_revision: str | tuple[str, ...] | None = "p7_open_010_user_projects_blocker3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # 1. utility_heat_exchange: 新增 medium_type + pressure_level 字段 (R1 §7.1 + §7.2)
    op.add_column(
        "utility_heat_exchange",
        sa.Column(
            "medium_type",
            sa.String(32),
            nullable=True,
            comment=(
                "介质类型 (R1 §7.2 GB 30251-2024 附录A 9 类水): "
                "FRESH_WATER / CIRCULATING_WATER / SOFTENED_WATER / DEMINERALIZED_WATER / "
                "LP_DEAERATED_WATER / HP_DEAERATED_WATER / TURBINE_CONDENSATE / "
                "120C_CONDENSATE_TREATED / 120C_CONDENSATE_REUSABLE / STEAM"
            ),
        ),
    )
    op.add_column(
        "utility_heat_exchange",
        sa.Column(
            "pressure_level",
            sa.String(32),
            nullable=True,
            comment=(
                "压力等级 (R1 §7.1 GB 30251-2024 附录A 9 档蒸汽): "
                "GE_7_0_MPA / 4_5_TO_7_0_MPA / 3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / "
                "1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / 0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / "
                "LT_0_3_MPA (R0 旧 temperature_class LP/MP/HP/ULTRA_HIGH 已 deprecated)"
            ),
        ),
    )
    op.create_index(
        "ix_utility_heat_exchange_medium_type",
        "utility_heat_exchange",
        ["medium_type"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_utility_heat_exchange_pressure_level",
        "utility_heat_exchange",
        ["pressure_level"],
        if_not_exists=True,
    )

    # 2. utility_fuel_gas: 新增 gas_source 字段 (R1 §7.3)
    op.add_column(
        "utility_fuel_gas",
        sa.Column(
            "gas_source",
            sa.String(32),
            nullable=True,
            comment=(
                "气源分类 (R1 §7.3 GB 30251-2024 附录A): "
                "OILFIELD_GAS (油田气 0.93) / GASFIELD_GAS (气田气 0.85) / "
                "REFINERY_FUEL_GAS (炼厂燃料气 950 kg/t) (R0 旧 fuel_type NATURAL_GAS 已 deprecated)"
            ),
        ),
    )
    op.create_index(
        "ix_utility_fuel_gas_gas_source",
        "utility_fuel_gas",
        ["gas_source"],
        if_not_exists=True,
    )

    # 3. utility_energy_summary: 新增 electricity_value_type 字段 (R1 §5)
    op.add_column(
        "utility_energy_summary",
        sa.Column(
            "electricity_value_type",
            sa.String(16),
            nullable=True,
            comment=(
                "电当量值/等价值选择 (R1 §5 GB 30251-2024 §6.1.1): "
                "EQUIVALENT (当量值 0.086 kg标油/kWh - 其他产品用) / "
                "EQUIVALENT_VALUE (等价值 0.21 kg标油/kWh - 炼油/乙烯用); "
                "NULL = 默认 EQUIVALENT"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("utility_energy_summary", "electricity_value_type")
    op.drop_index("ix_utility_fuel_gas_gas_source", "utility_fuel_gas", if_exists=True)
    op.drop_column("utility_fuel_gas", "gas_source")
    op.drop_index(
        "ix_utility_heat_exchange_pressure_level", "utility_heat_exchange",
        if_exists=True,
    )
    op.drop_index(
        "ix_utility_heat_exchange_medium_type", "utility_heat_exchange",
        if_exists=True,
    )
    op.drop_column("utility_heat_exchange", "pressure_level")
    op.drop_column("utility_heat_exchange", "medium_type")
