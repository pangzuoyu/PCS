"""P5-0-2 Task 2: heat_results 双轨字段扩展（ADR-0027 V1.0）。

按 ADR-0027 V1.0 决策 1/5：
1. **旧轨 9 标量保留**（P5-OPEN-006 向后兼容承诺）：
   equipment_no / equipment_name / **duty** / effective_area / hot_inlet_pressure /
   hot_outlet_pressure / cold_inlet_pressure / cold_outlet_pressure / u_overall
2. **新轨 39 标量 + 3 JSONB**（SUP-009 V1.0 §3.1）：
   - 基础标识 7：exchanger_type / orientation / units_series / units_parallel /
     shells_per_unit / total_area_gross / total_area_eff
   - 通用热工 8：lmtd / mtd_corrected / emtd / overdesign_percent / u_service /
     u_calculated / u_clean / heat_exchange_area
     （**`duty` 与 9 旧共享 1 列**，本迁移不重复加；详 ADR-0027 决策 5）
   - 通用几何 9：tube_count / tube_od / tube_id / tube_wall_thickness / tube_length /
     tube_pitch / tube_layout / tube_material / tube_passes
   - 壳程几何 10：shell_id / shell_design_pressure / shell_design_temp / baffle_type /
     baffle_cut_percent / baffle_spacing / baffle_inlet_spacing / seal_strip_count /
     passlane_seal_rod_count / impingement_plate
   - 热阻分布 5：thermal_resistance_shell / tube / fouling / metal / bond
   - 3 JSONB：shell_params（§3.1.3 壳程物性）/ tube_params（§3.1.3 管程物性）/
     ache_params（§3.1.7 空冷器专属）

**列数**：本迁移新增 9 旧（含 duty） + 39 新标量（除 duty） + 3 JSONB = **51 列**。
其中 9 旧 `duty` 与 SUP-009 §3.1.2 `duty` 共享 1 列（合并 = 9 旧名）。

**新轨总字段 = 39 标量 + 3 JSONB = 42 新字段**（ADR-0027 决策 5）。

**P5-0 批约束 3（Q4）修订**：Task 2 后 REGISTRY 9 → 10（+HeatResult，修正 P4 遗漏）。
原"P5-0-1b 后 = 13" 修订为"= 14"（13 + HeatResult）。

**SPEC V1.2 §4.1 9 JSONB 缺口**：general / performance / heat_transfer / construction /
tube_bundle / shell_internals / weights / material / connections — 与 ORM 现状 5 JSONB
语义不对应，列为 P5+ backlog（本迁移不补，详 ADR-0027 决策 4）。

**DOWN-REVISION** = p5_0_5_psv_multi_standard（P5-0-5 末态）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p5_0_2_heat_results_extend"
down_revision = "p5_0_5_psv_multi_standard"
branch_labels = None
depends_on = None


# 9 旧标量（P5-OPEN-006 保留列）
_LEGACY_9_COLUMNS: list[tuple[str, sa.types.TypeEngine, bool]] = [
    ("equipment_no", sa.String(length=30), True),
    ("equipment_name", sa.String(length=100), True),
    ("duty", sa.Float(), True),  # 与新轨共享 1 列（详 ADR-0027 决策 5）
    ("effective_area", sa.Float(), True),
    ("hot_inlet_pressure", sa.Float(), True),
    ("hot_outlet_pressure", sa.Float(), True),
    ("cold_inlet_pressure", sa.Float(), True),
    ("cold_outlet_pressure", sa.Float(), True),
    ("u_overall", sa.Float(), True),
]

# 39 新标量（除 duty 共享 9 旧），按 SUP-009 §3.1.1-3.1.6 分组
_NEW_39_SCALARS: list[tuple[str, sa.types.TypeEngine, bool]] = [
    # §3.1.1 基础标识 7
    ("exchanger_type", sa.String(length=20), True),
    ("orientation", sa.String(length=20), True),
    ("units_series", sa.Integer(), True),
    ("units_parallel", sa.Integer(), True),
    ("shells_per_unit", sa.Integer(), True),
    ("total_area_gross", sa.Float(), True),
    ("total_area_eff", sa.Float(), True),
    # §3.1.2 通用热工 8（除 duty 共享 9 旧）
    ("lmtd", sa.Float(), True),
    ("mtd_corrected", sa.Float(), True),
    ("emtd", sa.Float(), True),
    ("overdesign_percent", sa.Float(), True),
    ("u_service", sa.Float(), True),
    ("u_calculated", sa.Float(), True),
    ("u_clean", sa.Float(), True),
    ("heat_exchange_area", sa.Float(), True),
    # §3.1.4 通用几何 9
    ("tube_count", sa.Integer(), True),
    ("tube_od", sa.Float(), True),
    ("tube_id", sa.Float(), True),
    ("tube_wall_thickness", sa.Float(), True),
    ("tube_length", sa.Float(), True),
    ("tube_pitch", sa.Float(), True),
    ("tube_layout", sa.String(length=10), True),
    ("tube_material", sa.String(length=100), True),
    ("tube_passes", sa.Integer(), True),
    # §3.1.5 壳程几何 10
    ("shell_id", sa.Float(), True),
    ("shell_design_pressure", sa.Float(), True),
    ("shell_design_temp", sa.Float(), True),
    ("baffle_type", sa.String(length=30), True),
    ("baffle_cut_percent", sa.Float(), True),
    ("baffle_spacing", sa.Float(), True),
    ("baffle_inlet_spacing", sa.Float(), True),
    ("seal_strip_count", sa.Integer(), True),
    ("passlane_seal_rod_count", sa.Integer(), True),
    ("impingement_plate", sa.String(length=10), True),
    # §3.1.6 热阻分布 5
    ("thermal_resistance_shell", sa.Float(), True),
    ("thermal_resistance_tube", sa.Float(), True),
    ("thermal_resistance_fouling", sa.Float(), True),
    ("thermal_resistance_metal", sa.Float(), True),
    ("thermal_resistance_bond", sa.Float(), True),
]

# 3 新 JSONB（SUP-009 §3.1.3 + §3.1.7）
_NEW_3_JSONB: list[tuple[str]] = [
    ("shell_params",),  # §3.1.3 壳程工艺物性
    ("tube_params",),   # §3.1.3 管程工艺物性
    ("ache_params",),   # §3.1.7 空冷器专属
]


def upgrade() -> None:
    # 1. 9 旧标量
    for col_name, col_type, nullable in _LEGACY_9_COLUMNS:
        op.add_column(
            "heat_results",
            sa.Column(col_name, col_type, nullable=nullable),
        )

    # 2. 39 新标量
    for col_name, col_type, nullable in _NEW_39_SCALARS:
        op.add_column(
            "heat_results",
            sa.Column(col_name, col_type, nullable=nullable),
        )

    # 3. 3 新 JSONB
    for (col_name,) in _NEW_3_JSONB:
        op.add_column(
            "heat_results",
            sa.Column(col_name, JSONB, nullable=True),
        )


def downgrade() -> None:
    # 1. 3 JSONB 回退
    for (col_name,) in reversed(_NEW_3_JSONB):
        op.drop_column("heat_results", col_name)

    # 2. 39 新标量回退
    for col_name, _, _ in reversed(_NEW_39_SCALARS):
        op.drop_column("heat_results", col_name)

    # 3. 9 旧标量回退
    for col_name, _, _ in reversed(_LEGACY_9_COLUMNS):
        op.drop_column("heat_results", col_name)
