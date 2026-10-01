"""P7 Sprint 2 R1 修订: EnergyAggregation 入库持久化 (F-P0-001 R1 §7)

Per PCS-SIGN-F-P0-001-2026-10-08-R1 §7 + service 落地:
- utility_energy_summary 新增 r1_classification_json JSONB 字段
  持久化 R1 分类聚合结果 (3 类 dict):
  - steam_by_pressure_level: 9 档蒸汽 (GE_7_0_MPA → LT_0_3_MPA) → annual_consumption_t
  - fuel_gas_by_source: 3 类气源 (OILFIELD_GAS / GASFIELD_GAS / REFINERY_FUEL_GAS) → annual_consumption_nm3
  - water_by_type: 9 类水 (FRESH_WATER → 120C_CONDENSATE_REUSABLE) → annual_consumption_t
  (待 P7-6B 冷却水子表落地 water_by_type 数据)

设计要点 (per Do-Not-Repeat): 3 dict 字段合并到 1 JSONB 容器,
避免 3 次单列迁移 + 减少表宽度爆炸 (water 子表未落地, 留 nullable).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "p7_open_012_r1_classification_persist"
down_revision: str | tuple[str, ...] | None = "p7_open_010_r1_classification_fields"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # utility_energy_summary: 新增 r1_classification_json JSONB 字段 (R1 §7 入库)
    op.add_column(
        "utility_energy_summary",
        sa.Column(
            "r1_classification_json",
            JSONB,
            nullable=True,
            comment=(
                "R1 分类聚合结果 (F-P0-001 R1 §7): "
                "{steam_by_pressure_level: {GE_7_0_MPA: float}, "
                "fuel_gas_by_source: {OILFIELD_GAS: float}, "
                "water_by_type: {FRESH_WATER: float}}; "
                "null = R0 单值聚合 (向后兼容)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("utility_energy_summary", "r1_classification_json")