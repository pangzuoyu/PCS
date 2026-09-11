"""P3.x SIM-33: 气相物性 9 字段（ORM 列） + 液相物性命名对齐 + SIM-31 JSONB 3 字段迁 ORM。

spec §1.2.1 + ADD-001 §3.5/§3.6：

**液相命名对齐**（path 1: alembic RENAME COLUMN，与 spec §3.6 liquid_ 前缀规范对齐）：
- density → liquid_density
- viscosity_dynamic → liquid_viscosity_dynamic
- viscosity_kinematic → liquid_viscosity_kinematic
- thermal_conductivity → liquid_thermal_conductivity
- specific_heat → liquid_specific_heat
- surface_tension → liquid_surface_tension
- compressibility_factor → liquid_compressibility_factor
  （与 vapor_z 对称；通用 Z 因 vapor_z 已存在，此处取 liquid 侧命名）
- molecular_weight：不动（通用 MW，气液相同）

**SIM-31 JSONB → ORM 迁移**（path 1 协同：避免气液不对称）：
- std_liq_density → liquid_std_density（重命名 + JSONB 提升 ORM）
- liquid_mass_rate → liquid_mass_rate（重命名已在 SIM-31 完成；保持 + JSONB 提升 ORM）
- liq_actual_m3hr → liquid_actual_m3hr（重命名 + JSONB 提升 ORM）

**气相 9 字段 C/O**（ADD-001 §3.5，与 vapor_fraction ORM 模式一致）：
- vapor_mass_rate, vapor_actual_m3hr, vapor_normal_m3hr
- vapor_mw, vapor_density, vapor_z
- vapor_cp, vapor_viscosity, vapor_thermal_cond

down_revision = p3sim_streams_liquid_fields
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p3sim_streams_vapor_fields"
down_revision = "p3sim_streams_liquid_fields"
branch_labels = None
depends_on = None


# 列重命名（液相命名对齐 spec §3.6）
_LIQUID_RENAMES = (
    ("density", "liquid_density", "液相密度 kg/m³（spec §3.6）"),
    ("viscosity_dynamic", "liquid_viscosity_dynamic", "液相动力粘度 Pa·s（spec §3.6）"),
    ("viscosity_kinematic", "liquid_viscosity_kinematic", "液相运动粘度 m²/s（spec §3.6）"),
    ("thermal_conductivity", "liquid_thermal_conductivity", "液相导热系数 W/(m·K)（spec §3.6）"),
    ("specific_heat", "liquid_specific_heat", "液相比热容 kJ/(kg·K)（spec §3.6）"),
    ("surface_tension", "liquid_surface_tension", "液相表面张力 N/m（spec §3.6）"),
    ("compressibility_factor", "liquid_compressibility_factor", "液相压缩因子 Z（与 vapor_z 对称）"),
)


# 新增列：气相 9 字段（spec §3.5）+ SIM-31 JSONB 提升 ORM 的 3 字段
_NEW_VAPOR_COLUMNS = (
    ("vapor_mass_rate", "气相质量流量 kg/h"),
    ("vapor_actual_m3hr", "气相实际体积流量 m³/h"),
    ("vapor_normal_m3hr", "气相标况体积流量 Nm³/h"),
    ("vapor_mw", "气相分子量"),
    ("vapor_density", "气相密度 kg/m³"),
    ("vapor_z", "气相压缩因子 Z"),
    ("vapor_cp", "气相比热容 kJ/(kg·K)"),
    ("vapor_viscosity", "气相动力粘度 Pa·s"),
    ("vapor_thermal_cond", "气相导热系数 W/(m·K)"),
)


# SIM-31 JSONB 字段迁 ORM（重命名 + 提升 ORM）
_NEW_LIQUID_FROM_JSONB = (
    ("liquid_std_density", "液相标况密度 kg/m³（spec §3.6，SIM-31 JSONB→ORM）"),
    ("liquid_mass_rate", "液相质量流量 kg/h（SIM-31 JSONB→ORM）"),
    ("liquid_actual_m3hr", "液相实际体积流量 m³/h（SIM-31 JSONB→ORM）"),
)


def upgrade() -> None:
    # 1. 液相 7 列重命名（spec §3.6 liquid_ 前缀）
    for old, new, _ in _LIQUID_RENAMES:
        op.alter_column(
            "streams",
            old,
            new_column_name=new,
        )

    # 2. 新增气相 9 列（spec §3.5 C/O）
    for col, comment in _NEW_VAPOR_COLUMNS:
        op.add_column(
            "streams",
            sa.Column(col, sa.Float(), nullable=True, comment=comment),
        )

    # 3. 新增 SIM-31 JSONB → ORM 3 列（避免气液不对称）
    for col, comment in _NEW_LIQUID_FROM_JSONB:
        op.add_column(
            "streams",
            sa.Column(col, sa.Float(), nullable=True, comment=comment),
        )


def downgrade() -> None:
    # 1. 移除 SIM-31 JSONB → ORM 3 列
    for col, _ in _NEW_LIQUID_FROM_JSONB:
        op.drop_column("streams", col)

    # 2. 移除气相 9 列
    for col, _ in _NEW_VAPOR_COLUMNS:
        op.drop_column("streams", col)

    # 3. 液相 7 列重命名回原名
    for old, new, _ in reversed(_LIQUID_RENAMES):
        op.alter_column(
            "streams",
            new,
            new_column_name=old,
        )