"""P5-0-2 Task 2: heat_results 双轨字段扩展 + REGISTRY 10 类 contract 测试。

按 ADR-0027 V1.0（决策 1/2/5）：

**双轨结构**：
- 9 旧标量（P5-OPEN-006 向后兼容）：equipment_no / equipment_name / **duty** /
  effective_area / hot_inlet_pressure / hot_outlet_pressure / cold_inlet_pressure /
  cold_outlet_pressure / u_overall
- 5 现状 JSONB：air_side_json / design_conditions_json / enthalpy_table_json /
  input_json / output_json（P3 通用 + P4 早期实施，保留）
- 39 新标量 + 3 新 JSONB（SUP-009 V1.0 §3.1）：`duty` 与 9 旧共享 1 列

**本测试覆盖**：
1. HeatResult ORM 字段完整性：9 旧 + 5 现状 + 39 新标量 + 3 新 JSONB
2. `duty` 共享 1 列（既在 9 旧列表也在新标量中，但 ORM 只 1 列）
3. RECORD_TYPE_REGISTRY == 10（Q4 约束 3 修订：原 13 → 14 因 +HeatResult）
4. alembic migration 51 列（9+39+3）+ down_revision 链
5. 5 现状 JSONB 列未丢失
"""
from __future__ import annotations

from pathlib import Path

from app.models.calc import HeatResult
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_MIGRATION_PATH = (
    ROOT / "alembic" / "alembic" / "versions" / "p5_0_2_heat_results_extend.py"
)
ALEMBIC_MIGRATION_PATH_FALLBACK = (
    ROOT / "alembic" / "versions" / "p5_0_2_heat_results_extend.py"
)

# 9 旧标量（P5-OPEN-006 保留列）
LEGACY_9_COLUMNS: frozenset[str] = frozenset({
    "equipment_no",
    "equipment_name",
    "duty",  # 与新轨共享 1 列（详 ADR-0027 决策 5）
    "effective_area",
    "hot_inlet_pressure",
    "hot_outlet_pressure",
    "cold_inlet_pressure",
    "cold_outlet_pressure",
    "u_overall",
})

# 5 现状 JSONB（P3 通用 + P4 早期，保留非旧字段）
EXISTING_5_JSONB: frozenset[str] = frozenset({
    "air_side_json",
    "design_conditions_json",
    "enthalpy_table_json",
    "input_json",
    "output_json",
})

# 39 新标量（SUP-009 §3.1.1-3.1.6，**除 duty 共享 9 旧**）
NEW_39_SCALARS: frozenset[str] = frozenset({
    # §3.1.1 基础标识 7
    "exchanger_type", "orientation", "units_series", "units_parallel",
    "shells_per_unit", "total_area_gross", "total_area_eff",
    # §3.1.2 通用热工 8（除 duty）
    "lmtd", "mtd_corrected", "emtd", "overdesign_percent",
    "u_service", "u_calculated", "u_clean", "heat_exchange_area",
    # §3.1.4 通用几何 9
    "tube_count", "tube_od", "tube_id", "tube_wall_thickness",
    "tube_length", "tube_pitch", "tube_layout", "tube_material", "tube_passes",
    # §3.1.5 壳程几何 10
    "shell_id", "shell_design_pressure", "shell_design_temp", "baffle_type",
    "baffle_cut_percent", "baffle_spacing", "baffle_inlet_spacing",
    "seal_strip_count", "passlane_seal_rod_count", "impingement_plate",
    # §3.1.6 热阻分布 5
    "thermal_resistance_shell", "thermal_resistance_tube",
    "thermal_resistance_fouling", "thermal_resistance_metal",
    "thermal_resistance_bond",
})

# 3 新 JSONB（SUP-009 §3.1.3 + §3.1.7）
NEW_3_JSONB: frozenset[str] = frozenset({
    "shell_params",  # §3.1.3 壳程工艺物性
    "tube_params",   # §3.1.3 管程工艺物性
    "ache_params",   # §3.1.7 ACHE 专属
})


def _migration_path() -> Path:
    for candidate in (ALEMBIC_MIGRATION_PATH, ALEMBIC_MIGRATION_PATH_FALLBACK):
        if candidate.exists():
            return candidate
    return ALEMBIC_MIGRATION_PATH_FALLBACK  # 报 file_exists 失败时使用


# ============================================================================
# 1. ORM 字段完整性
# ============================================================================


def test_heat_result_tablename():
    assert HeatResult.__tablename__ == "heat_results"


def test_heat_result_has_9_legacy_columns():
    """9 旧标量（P5-OPEN-006 保留列）必须存在。"""
    cols = frozenset(HeatResult.__table__.columns.keys())
    assert LEGACY_9_COLUMNS <= cols, (
        f"HeatResult 缺 9 旧标量: {LEGACY_9_COLUMNS - cols}"
    )


def test_heat_result_has_5_existing_jsonb():
    """5 现状 JSONB 必须保留（不删不重构）。"""
    cols = frozenset(HeatResult.__table__.columns.keys())
    assert EXISTING_5_JSONB <= cols, (
        f"HeatResult 缺 5 现状 JSONB: {EXISTING_5_JSONB - cols}"
    )


def test_heat_result_has_39_new_scalars():
    """39 新标量（SUP-009 §3.1，**除 duty 共享 9 旧**）必须存在。"""
    cols = frozenset(HeatResult.__table__.columns.keys())
    assert NEW_39_SCALARS <= cols, (
        f"HeatResult 缺 39 新标量: {NEW_39_SCALARS - cols}"
    )


def test_heat_result_has_3_new_jsonb():
    """3 新 JSONB（SUP-009 §3.1.3 + §3.1.7）必须存在。"""
    cols = frozenset(HeatResult.__table__.columns.keys())
    assert NEW_3_JSONB <= cols, (
        f"HeatResult 缺 3 新 JSONB: {NEW_3_JSONB - cols}"
    )


def test_duty_column_shared_only_once():
    """`duty` 必须只 1 列（与 9 旧共享 1 列，不是 2 列）。"""
    duty_cols = [
        c.name for c in HeatResult.__table__.columns if c.name == "duty"
    ]
    assert len(duty_cols) == 1, (
        f"`duty` 必须 1 列（与 9 旧共享），实际 {len(duty_cols)} 列"
    )


# ============================================================================
# 2. RECORD_TYPE_REGISTRY == 10（Q4 约束 3 修订）
# ============================================================================


def test_record_type_registry_count_is_10():
    """P5-0 批约束 3 修订：Task 2 后 REGISTRY 必须 10 类（+ HeatResult）。

    Q4 约束 3 原"P5-0-1b 后=13"修订为"=14"（13 + HeatResult 修正 P4 遗漏）。
    **P5-1-4 修订**（ADR-0032 V1.1 决策 6）：+VesselResult → 11 类。
    **P5-2-4 修订**：+SepEquipResult → 12 类。
    """
    assert len(RECORD_TYPE_REGISTRY) == 12, (
        f"REGISTRY 应 12 类（P5-2-4 +SepEquipResult），实际 {len(RECORD_TYPE_REGISTRY)}: "
        f"{list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_contains_heat_result():
    """REGISTRY 必须包含 HeatResult（P5-0-2 新增，修正 P4 遗漏）。"""
    assert "HeatResult" in RECORD_TYPE_REGISTRY, (
        f"REGISTRY 缺 HeatResult: {list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_contains_vessel_result():
    """P5-1-4：REGISTRY 必须包含 VesselResult。"""
    assert "VesselResult" in RECORD_TYPE_REGISTRY, (
        f"REGISTRY 缺 VesselResult: {list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_contains_sep_equip_result():
    """P5-2-4：REGISTRY 必须包含 SepEquipResult（旋风/丝网/重力/VANE/FIBER 共用）。"""
    assert "SepEquipResult" in RECORD_TYPE_REGISTRY, (
        f"REGISTRY 缺 SepEquipResult: {list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_preserves_p5_0_5_9_classes():
    """REGISTRY 12 类必须包含 P5-0-5 末态 9 类 + P5-1-4 VesselResult + P5-2-4 SepEquipResult。"""
    expected_p5_0_5 = {
        "PipingResult", "PumpResult", "FlashResult", "PipeNetworkResult",
        "TwoPhaseResult", "ReliefResult", "ColumnSizingResult", "MixerResult",
        "ProjectCalculationStandardProfile",
        "VesselResult", "SepEquipResult",
    }
    assert expected_p5_0_5 <= set(RECORD_TYPE_REGISTRY.keys()), (
        f"REGISTRY 缺 P5-0-5 9 类 + P5-1-4 VesselResult + P5-2-4 SepEquipResult: "
        f"{expected_p5_0_5 - set(RECORD_TYPE_REGISTRY.keys())}"
    )


# ============================================================================
# 3. alembic migration 结构
# ============================================================================


def test_alembic_migration_file_exists():
    path = _migration_path()
    assert path.exists(), f"P5-0-2 alembic 迁移文件缺失: {path}"


def test_alembic_revision_and_down_revision():
    """revision = p5_0_2_heat_results_extend，down_revision = p5_0_5_psv_multi_standard。"""
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    assert 'revision = "p5_0_2_heat_results_extend"' in content
    assert 'down_revision = "p5_0_5_psv_multi_standard"' in content, (
        "down_revision 必须为 P5-0-5 末态（p5_0_5_psv_multi_standard）"
    )


def test_alembic_migration_adds_51_columns():
    """alembic 迁移加 51 列（9 旧 + 39 新 + 3 JSONB）。

    列名出现在模块级 _LEGACY_9_COLUMNS / _NEW_39_SCALARS / _NEW_3_JSONB
    tuple 定义中（被循环用于 op.add_column）。
    """
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    # 9 旧 + 39 新 + 3 新 JSONB = 51 列
    all_51: set[str] = (
        LEGACY_9_COLUMNS | NEW_39_SCALARS | NEW_3_JSONB
    )
    assert len(all_51) == 51, (
        f"51 列集合去重后应 51 个，实际 {len(all_51)}"
    )
    for col_name in all_51:
        assert f'"{col_name}"' in content, (
            f"alembic 缺列 {col_name}（tuple 定义中未找到）"
        )


def test_alembic_migration_preserves_5_existing_jsonb():
    """alembic 不应删除 5 现状 JSONB（双轨保留）。"""
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    for jb in EXISTING_5_JSONB:
        assert f"op.drop_column.{jb}" not in content and f'drop_column.{jb}' not in content, (
            f"alembic 不应 drop_column {jb}（双轨保留）"
        )


def test_alembic_migration_keeps_duty_single_column():
    """alembic 必须只声明 1 次 `duty` 列（9 旧包含 duty，新轨不重复加）。

    `duty` 出现在 _LEGACY_9_COLUMNS tuple 中（1 次 tuple 定义）；不应再
    出现在 _NEW_39_SCALARS 区域（否则 2 次 add_column = 2 列）。
    """
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    duty_quote_count = content.count('"duty"')
    assert duty_quote_count == 1, (
        f"`duty` 必须只 1 次 tuple 定义，实际 {duty_quote_count} 次（"
        f"9 旧包含 duty，新轨不应重复）"
    )
    # 防回归：duty 不出现在 39 新标量列表（如果在，quote_count 会 > 1）
    assert '"duty"' not in content.split("_NEW_39_SCALARS")[1], (
        "`duty` 不应在 _NEW_39_SCALARS 区域（已共享 9 旧）"
    )
