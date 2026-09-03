"""add pcs_toe_conversion_factors

Revision ID: 2026_09_03_0800_add_toe_conversion
Revises: p2_sprint2_equipment_procurement_delivery
Create Date: 2026-09-03

V1.4 P2-OPEN-005：折标煤系数组，配套 SUP-008 §2.5 + SUP-010 §3.3.4。
"""
from alembic import op
import sqlalchemy as sa

revision = "2026_09_03_0800_add_toe_conversion"
down_revision = "p2_sprint2_equipment_procurement_delivery"


def upgrade():
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
    op.drop_table("pcs_toe_conversion_factors")