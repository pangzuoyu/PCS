"""p7_s3_003: config_energy_conversion_factors 补 R1 分类列 (从未迁移的 schema drift).

发现 (2026-10-05, 查标准一致性时顺带查出):
    `app/models/config.py::ConfigEnergyConversionFactor` 声明了
    value_type / sub_type / pressure_level / water_type 4 列 + 复合 UNIQUE,
    **但没有任何 migration 创建过它们**。真实库 (pcs / pcs_test) 该表只有 9 列:
        id, energy_type, toe_factor, standard_coal_factor, source,
        confirmed_by, confirmed_at, created_at, updated_at
    且行数为 0 —— T0 seed 脚本从未在真实库跑成功过。

后果 (测试全绿掩盖了它):
    - `_get_factors_by_classification` 按 sub_type/pressure_level/water_type/
      value_type 查表 → 真实库上会 UndefinedColumn
    - 整条 R1 26 行折标机制**只在 in-memory SQLite 测试里成立**
    - T5 综合能耗在真实库上算不出折标系数

`p7_open_010_r1_classification_fields.py` 名字像是做这件事的, 但它只改了
utility_energy_summary / utility_fuel_gas / utility_heat_exchange 三张表,
**没碰 config_energy_conversion_factors**。本 migration 补上这个缺口。

Revision ID: p7_s3_003
Revises: p7_s3_002
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_003"
down_revision = "p7_s3_002"
branch_labels = None
depends_on = None

_TABLE = "config_energy_conversion_factors"
_CONSTRAINT = "uq_config_energy_conversion_factors_classification"
# R0 遗留约束: p7_open_009_t0 建表时按「一能源类型一行」设计, 加了
# UNIQUE(energy_type)。R1 改成「一能源类型多行」(电2/燃料气3/蒸汽9/水9/空气2),
# ORM 已换成复合 UNIQUE, 但**没有任何 migration drop 掉这条 R0 约束** →
# 真实库上第二个 STEAM 行就 UniqueViolation, 26 行永远灌不进去。
# 本 migration 一并 drop。
_R0_CONSTRAINT = "uq_config_energy_conversion_factors_energy_type"


def upgrade() -> None:
    """Drop R0 UNIQUE(energy_type) + 加 4 个分类列 + 复合 UNIQUE + energy_type 索引."""
    op.drop_constraint(
        _R0_CONSTRAINT, _TABLE, type_="unique", if_exists=True
    )

    for col, comment in (
        (
            "value_type",
            "电当量/等价值 (GB 30251-2024 §6.1.5): "
            "ELECTRICITY: EQUIVALENT / EQUIVALENT_VALUE; 其他能源: NULL",
        ),
        (
            "sub_type",
            "子类: FUEL_GAS: OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS; "
            "FUEL: FUEL_OIL/LPG/METHANE_H2/PSA_OFF_GAS/CATALYTIC_COKE/"
            "PETROLEUM_COKE; INSTRUMENT_AIR: PURIFIED/NON_PURIFIED",
        ),
        (
            "pressure_level",
            "蒸汽压力等级 (GB 30251-2024 附录A 9 档): GE_7_0_MPA / 4_5_TO_7_0_MPA / "
            "3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / 1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / "
            "0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / LT_0_3_MPA",
        ),
        (
            "water_type",
            "水类型 (GB 30251-2024 附录A 9 类): FRESH_WATER / CIRCULATING_WATER / "
            "SOFTENED_WATER / DEMINERALIZED_WATER / LP_DEAERATED_WATER / "
            "HP_DEAERATED_WATER / TURBINE_CONDENSATE / 120C_CONDENSATE_TREATED / "
            "120C_CONDENSATE_REUSABLE",
        ),
    ):
        op.add_column(
            _TABLE,
            sa.Column(col, sa.String(32), nullable=True, comment=comment),
        )

    op.create_unique_constraint(
        _CONSTRAINT,
        _TABLE,
        ["energy_type", "value_type", "sub_type", "pressure_level", "water_type"],
        if_not_exists=True,
    )
    # model 里 energy_type 声明了 index=True, 但真实库无此索引 (ORM 声明 ≠ alembic 建)
    op.create_index(
        "ix_config_energy_conversion_factors_energy_type",
        _TABLE,
        ["energy_type"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """删索引 + UNIQUE + 4 个分类列 (if_exists 幂等).

    **不恢复 R0 的 UNIQUE(energy_type)**: 恢复前必须先确认无同 energy_type 多行,
    否则 downgrade 本身会失败。留下比恢复更安全。

    ⚠️ **downgrade 有数据丢失**: drop_column 会抹掉所有行的 value_type /
    sub_type / pressure_level / water_type 值。往返 (downgrade→upgrade) 后
    26 行原始数据的分类值变 NULL, p7_s3_004 的 UPDATE 将匹配不到 → 需重跑
    T0 seed 脚本补回。行数不变, 但分类信息需重建。这是 drop_column 的固有
    代价, 非本 migration 特有。
    """
    op.drop_index(
        "ix_config_energy_conversion_factors_energy_type", table_name=_TABLE,
        if_exists=True,
    )
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique", if_exists=True)
    for col in ("value_type", "sub_type", "pressure_level", "water_type"):
        op.drop_column(_TABLE, col)
