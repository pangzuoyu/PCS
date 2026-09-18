"""add pcs_toe_conversion_factors
Revision ID: 2026_09_03_0800_add_toe_conversion
Revises: p2_sprint2_equipment_procurement_delivery
Create Date: 2026-09-03

V1.4 P2-OPEN-005：折标煤系数组，配套 SUP-008 §2.5 + SUP-010 §3.3.4。
"""
# ruff: noqa: E501 — 冻结迁移：种子 SQL VALUES 数据行天然超宽
import sqlalchemy as sa

from alembic import op

revision = "2026_09_03_0800_add_toe_conversion"
down_revision = "p2_sprint2_equipment_procurement_delivery"


def upgrade():
    """pcs_toe_conversion_factors 主表 + 默认 6 项 seed（V1.4 P2-OPEN-005）。

    步骤：
    - A. 创建主表 pcs_toe_conversion_factors：id PK autoinc / fuel_type(30) /
      toe_conversion_factor(10,4) / standard_coal_factor(10,4) /
      effective_year / effective_from Date / effective_to Date NULL /
      source(200) / version(50) default 'TOE-V1.0' / created_by UUID /
      created_at / updated_at（updated_at 在 p2_s110_fix_toe_timestamptz 矫正时区）
    - B. UQ(fuel_type, effective_year) — 同年同燃料唯一
    - C. 索引：fuel_type + effective_year（按年/燃料过滤）
    - D. 默认 seed 6 项：GAS/DIESEL/COAL/STEAM/ELECTRICITY/OTHER × 2026 年
      来源：GB 2589-2020 / 综合能耗计算通则（基于蜡油加氢—综合能耗.xlsx 实例）

    业务：折标煤系数组；配套 SUP-008 §2.5 + SUP-010 §3.3.4 能耗计算。
    """
    op.create_table(
        "pcs_toe_conversion_factors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fuel_type", sa.String(30), nullable=False, index=True),
        sa.Column("toe_conversion_factor", sa.Numeric(10, 4), nullable=False),
        sa.Column("standard_coal_factor", sa.Numeric(10, 4), nullable=False),
        sa.Column("effective_year", sa.Integer, nullable=False, index=True),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("version", sa.String(50), nullable=False, server_default="TOE-V1.0"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("fuel_type", "effective_year", name="uq_toe_fuel_year"),
    )
    # 默认 seed 6 个 fuel_type × 2026 年（基于蜡油加氢—综合能耗.xlsx 实例）
    op.execute("""
        INSERT INTO pcs_toe_conversion_factors
            (fuel_type, toe_conversion_factor, standard_coal_factor,
             effective_year, effective_from, source, version)
        VALUES
            ('GAS',         1.0000, 1.2143, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0'),
            ('DIESEL',      1.4571, 1.7714, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0'),
            ('COAL',        0.7143, 0.8667, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0'),
            ('STEAM',       0.1429, 0.1714, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0'),
            ('ELECTRICITY', 0.1229, 0.1486, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0'),
            ('OTHER',       1.0000, 1.2143, 2026, '2026-01-01', 'GB 2589-2020 / 综合能耗计算通则', 'TOE-V1.0')
    """)


def downgrade():
    """pcs_toe_conversion_factors 表删除（TOE 综合能耗转换因子 seed 落地逆向）。

    步骤：
    - DROP TABLE pcs_toe_conversion_factors

    业务：与 upgrade 互逆；TOE 系数（V1.0 GB 2589-2020 综合能耗计算通则）落表逆向
    操作，删除全部 6 行（HEAT_ELECTRICITY/STEAM/GAS/WATER 等介质类型）+ 表本身。
    """
    op.drop_table("pcs_toe_conversion_factors")