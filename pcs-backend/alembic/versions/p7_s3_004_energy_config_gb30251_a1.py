"""p7_s3_004: 折标系数对齐 GB 30251-2024 附录A 表A.1.

用户裁决 2026-10-05: 「先完成 1-3, 附录A 有而 PCS 未建模的按照标准增加」。

三处修正 + 8 行新增:
1. bug-136 — 除盐水 / 凝汽机凝结水 1.04 → 1.0 (附录A 序号25/28;
   grep 两份标准全文均无 1.04, 来源不明, 偏差 +4.00%)
2. bug-135 — 新增 LOW_TEMP_HEAT 行 0.012 kg标油/MJ (附录A 序号34);
   原 utility_energy_summary_service.py:523 硬编码 (0.0341, 0.0487)
   偏离 +184.2% 且量纲错 (0.0341 是 GB/T 2589 表A.2 热力当量值 kgce/MJ)
3. LPG — UtilityFuelGas.fuel_type 有 LPG 枚举但 CONFIG 无系数行
   → 查表静默落到气田气 0.85。新增 FUEL/LPG = 1200 (附录A 序号4)
4. 其余 5 行附录A 有而 PCS 未建模的按吨计燃料 (序号3/5/9/10/11)

按吨计的燃料归 energy_type="FUEL" 而非 "FUEL_GAS":
  _compute_totals 对 FUEL_GAS 是 `fuel_gas_by_source(Nm³) × toe_factor`,
  序号6/7 (油田气/气田气) 是按 Nm³, 序号8 (炼厂燃料气 950) 是按吨。
  若把 LPG 1200 (kg标油/t) 放成 FUEL_GAS/LPG, 一旦设 gas_source='LPG'
  就会算出 Nm³ × 1200。FUEL 不经过聚合 → 纯参考元数据, 零地雷。

Revision ID: p7_s3_004
Revises: p7_s3_003
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_004"
down_revision = "p7_s3_003"
branch_labels = None
depends_on = None

SOURCE = "GB_30251_2024_APPENDIX_A"
CONFIRMED_BY = "工艺室-工艺负责人-2026-10-08 (R1) + 2026-10-05 附录A 全表对齐"

# 1 kg标油 = 1.4286 kg标煤
_COAL = 1.4286

# (energy_type, sub_type, pressure_level, water_type, value_type, toe, 序号, 名称, 单位)
_NEW_ROWS: list[tuple] = [
    ("FUEL", "FUEL_OIL", None, None, None, 1000.0, 3, "燃料油", "t"),
    ("FUEL", "LPG", None, None, None, 1200.0, 4, "液化石油气", "t"),
    ("FUEL", "METHANE_H2", None, None, None, 1200.0, 5, "甲烷氢", "t"),
    ("FUEL", "PSA_OFF_GAS", None, None, None, 320.0, 9, "制氢PSA尾气", "t"),
    ("FUEL", "CATALYTIC_COKE", None, None, None, 950.0, 10, "催化烧焦", "t"),
    ("FUEL", "PETROLEUM_COKE", None, None, None, 800.0, 11, "石油焦", "t"),
    ("LOW_TEMP_HEAT", None, None, None, None, 0.012, 34, "低温热", "MJ"),
]

# bug-136: R1 签署值 1.04 → 附录A 原值 1.0
_WATER_FIXES: list[tuple] = [
    ("DEMINERALIZED_WATER", 1.0, 25, "除盐水"),
    ("TURBINE_CONDENSATE", 1.0, 28, "凝汽机凝结水"),
]


def upgrade() -> None:
    """UPDATE 2 行水系数到标准值 + INSERT 8 行附录A 原有而 PCS 未建模的行."""
    conn = op.get_bind()

    # 1. 修正水系数 (幂等: 重复执行结果相同)
    for water_type, toe, _seq, _name in _WATER_FIXES:
        conn.execute(
            sa.text(
                """
                UPDATE config_energy_conversion_factors
                   SET toe_factor = :toe,
                       standard_coal_factor = :coal,
                       source = :source
                 WHERE energy_type = 'WATER'
                   AND water_type = :water_type
                """
            ),
            {
                "toe": toe,
                "coal": toe * _COAL,
                "source": SOURCE,
                "water_type": water_type,
            },
        )

    # 2. 新增行 — ON CONFLICT DO NOTHING 保证幂等 (F-P3-002 教训)
    for et, st, pl, wt, vt, toe, *_ in _NEW_ROWS:
        exists = conn.execute(
            sa.text(
                """
                SELECT 1 FROM config_energy_conversion_factors
                 WHERE energy_type = :et
                   AND sub_type IS NOT DISTINCT FROM :st
                   AND pressure_level IS NOT DISTINCT FROM :pl
                   AND water_type IS NOT DISTINCT FROM :wt
                   AND value_type IS NOT DISTINCT FROM :vt
                """
            ),
            {"et": et, "st": st, "pl": pl, "wt": wt, "vt": vt},
        ).first()
        if exists:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO config_energy_conversion_factors
                    (energy_type, value_type, sub_type, pressure_level,
                     water_type, toe_factor, standard_coal_factor, source,
                     confirmed_by)
                VALUES
                    (:et, :vt, :st, :pl, :wt, :toe, :coal, :source, :by)
                """
            ),
            {
                "et": et,
                "vt": vt,
                "st": st,
                "pl": pl,
                "wt": wt,
                "toe": toe,
                "coal": toe * _COAL,
                "source": SOURCE,
                "by": CONFIRMED_BY,
            },
        )


def downgrade() -> None:
    """删 8 行新增 + 水系数不恢复 (恢复 1.04 会重新引入 bug-136 偏差)."""
    conn = op.get_bind()
    for et, st, _pl, _wt, _vt, _toe, _seq, _name, _unit in _NEW_ROWS:
        conn.execute(
            sa.text(
                """
                DELETE FROM config_energy_conversion_factors
                 WHERE energy_type = :et
                   AND sub_type IS NOT DISTINCT FROM :st
                """
            ),
            {"et": et, "st": st},
        )
