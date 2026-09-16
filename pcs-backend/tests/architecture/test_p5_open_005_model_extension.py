"""P5-0-1 Task 1: 模型扩展架构契约测试（SUP-008 §8.3.2/§8.3.3/§8.3.5 + §8.4 OPEN-009）。

本批（P5-0-1a）落地 3 张设备结果表 ORM + design_stage 下沉 + alembic 迁移 +
RECORD_TYPE_REGISTRY 5 → 8 类扩展。contract 门禁：

1. ORM 类存在性（3 主表）
2. 3 主表业务字段完整性（relief_results 13 字段 / column_sizing 12 字段 +
   design_stage / mixer_results 9 字段）
3. ReliefScenario 枚举值 = P5-OPEN-005 合并 6 态
4. column_sizing.design_stage（§8.4 OPEN-009 VESSEL/PSV/COLUMN 三表下沉）
5. column_sizing + mixer_results (project_id, *_tag) UNIQUE 约束
6. relief_results.selected_psv_id → psv_results FK
7. alembic migration 文件存在 + revision/down_revision 正确
8. 迁移脚本使用 IF NOT EXISTS / create_type=False 幂等保护
9. RECORD_TYPE_REGISTRY 8 类（5 既有 + 3 新增）
"""
from __future__ import annotations

from pathlib import Path

from app.models.calc import (
    ColumnSizingResult,
    MixerResult,
    ReliefResult,
)
from app.models.enums import ReliefScenario
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_MIGRATION_PATH = ROOT / "alembic" / "versions" / "p5_open_005_model_extension.py"

# P5-OPEN-005 合并 6 态（SUP-008 §8.3.2 原 4 态 + P5 合并版 +CLOSED_VALVE / +UPSET）
EXPECTED_RELIEF_SCENARIO_VALUES: frozenset[str] = frozenset({
    "FIRE",
    "CLOSED_VALVE",
    "REACTION_LOSS_OF_CONTROL",
    "BLOCKED_OUTLET",
    "COOLING_FAILURE",
    "UPSET",
})

# P5-0-1a 新增 3 类
P5_0_1A_REGISTRY_KEYS: frozenset[str] = frozenset({
    "ReliefResult",
    "ColumnSizingResult",
    "MixerResult",
})

# P5-0-1a 前 5 类（P4-TASK0 闭环）
LEGACY_REGISTRY_KEYS: frozenset[str] = frozenset({
    "PipingResult",
    "PumpResult",
    "FlashResult",
    "PipeNetworkResult",
    "TwoPhaseResult",
})

# 列字段集：业务字段精确清单（SUP-008 §8.3.2/§8.3.3/§8.3.5）
RELIEF_RESULT_COLUMNS: frozenset[str] = frozenset({
    "relief_id",
    "source_equipment_id",
    "relief_scenario",
    "reactor_volume",
    "reactor_diameter",
    "reactor_height",
    "gas_tight_pressure",
    "safety_factor",
    "relief_rate_tier_1",
    "relief_rate_tier_2",
    "relief_rate_tier_3",
    "required_relief_area",
    "selected_psv_id",
})

COLUMN_SIZING_COLUMNS: frozenset[str] = frozenset({
    "column_id",
    "tag_number",
    "column_name",
    "hysys_flooding_percent",
    "hysys_calc_diameter_mm",
    "selected_diameter_mm",
    "reference_diameter_mm",
    "tray_spacing_mm",
    "tray_count",
    "theoretical_tray_count",
    "overall_efficiency",
    "calc_date",
    "design_stage",  # §8.4 OPEN-009 下沉
})

MIXER_RESULT_COLUMNS: frozenset[str] = frozenset({
    "mixer_id",
    "mixer_tag",
    "mixer_name",
    "component_1_name",
    "component_1_flow",
    "component_2_name",
    "component_2_flow",
    "pressure_drop_kpa",
    "check_result",
})


# ============================================================================
# 1. ORM 类存在性
# ============================================================================


def test_relief_result_orm_exists():
    """ReliefResult ORM 类必须存在且继承 Base。"""
    from app.db.base import Base

    assert issubclass(ReliefResult, Base)
    assert ReliefResult.__tablename__ == "relief_results"


def test_column_sizing_result_orm_exists():
    """ColumnSizingResult ORM 类必须存在。"""
    from app.db.base import Base

    assert issubclass(ColumnSizingResult, Base)
    assert ColumnSizingResult.__tablename__ == "column_sizing"


def test_mixer_result_orm_exists():
    """MixerResult ORM 类必须存在。"""
    from app.db.base import Base

    assert issubclass(MixerResult, Base)
    assert MixerResult.__tablename__ == "mixer_results"


# ============================================================================
# 2. 字段完整性（13/13+1/9 字段全集对齐）
# ============================================================================


def test_relief_result_business_columns():
    """ReliefResult 13 业务字段必须齐全（含 selected_psv_id FK）。"""
    actual = frozenset(ReliefResult.__table__.columns.keys())
    # RecordMixin + project/workspace 列 + 13 业务列，全部应存在
    missing = RELIEF_RESULT_COLUMNS - actual
    assert not missing, f"ReliefResult 缺字段: {missing}"


def test_column_sizing_business_columns_with_design_stage():
    """ColumnSizingResult 12 业务字段 + design_stage 必须齐全（§8.4 OPEN-009）。"""
    actual = frozenset(ColumnSizingResult.__table__.columns.keys())
    missing = COLUMN_SIZING_COLUMNS - actual
    assert not missing, f"ColumnSizingResult 缺字段: {missing}"
    # design_stage 必须显式存在（§8.4 OPEN-009 VESSEL/PSV/COLUMN 三表下沉）
    assert "design_stage" in actual, "ColumnSizingResult 必须含 design_stage 列"


def test_mixer_result_business_columns():
    """MixerResult 9 业务字段必须齐全。"""
    actual = frozenset(MixerResult.__table__.columns.keys())
    missing = MIXER_RESULT_COLUMNS - actual
    assert not missing, f"MixerResult 缺字段: {missing}"


# ============================================================================
# 3. ReliefScenario 枚举值
# ============================================================================


def test_relief_scenario_has_6_values():
    """ReliefScenario 枚举必须有 P5-OPEN-005 合并 6 态全集。"""
    actual = frozenset(s.value for s in ReliefScenario)
    assert len(actual) == 6, (
        f"ReliefScenario 应有 6 态，实际 {len(actual)}: {actual}"
    )
    assert actual == EXPECTED_RELIEF_SCENARIO_VALUES, (
        f"ReliefScenario 值集合与 P5-OPEN-005 不一致。"
        f"缺: {EXPECTED_RELIEF_SCENARIO_VALUES - actual}, "
        f"多: {actual - EXPECTED_RELIEF_SCENARIO_VALUES}"
    )


# ============================================================================
# 4. 设计阶段列下沉（§8.4 OPEN-009）
# ============================================================================


def test_column_sizing_design_stage_type_is_design_stage_enum():
    """column_sizing.design_stage 列类型必须是 design_stage_enum（PG enum 共享）。"""
    col = ColumnSizingResult.__table__.columns["design_stage"]
    # PG enum 共享：与 vessel_results / psv_results / pump_results 同 enum 类型
    # SQLAlchemy Enum 类型属性 .name 为 PG enum 名（str(col.type) 在 PG dialect 下
    # 渲染为 'VARCHAR(6)' 而非 enum 名，需用 .name 取真实 enum name）
    assert col.type.name == "design_stage_enum", (
        f"column_sizing.design_stage 应为 design_stage_enum，实际 {col.type.name}"
    )
    assert not col.nullable, "column_sizing.design_stage NOT NULL（与 vessel/psv/pump 同）"


# ============================================================================
# 5. UNIQUE 约束 + FK 关系
# ============================================================================


def test_column_sizing_unique_constraint_in_migration():
    """(project_id, column_tag) UNIQUE 约束必须在迁移脚本中（SUP-008 §8.3.3）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'uq_column_sizing_tag' in content, (
        "迁移脚本缺 column_sizing UNIQUE(project_id, column_tag) 约束"
    )
    assert 'uq_mixer_results_tag' in content, (
        "迁移脚本缺 mixer_results UNIQUE(project_id, mixer_tag) 约束"
    )


def test_relief_result_selected_psv_id_foreign_key():
    """relief_results.selected_psv_id 必须 FK → psv_results.psv_id（SUP-008 §8.3.2）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'ForeignKey("psv_results.psv_id")' in content, (
        "迁移脚本缺 selected_psv_id → psv_results FK"
    )


# ============================================================================
# 6. alembic 迁移契约
# ============================================================================


def test_alembic_migration_file_exists():
    """P5-0-1a alembic 迁移文件必须存在。"""
    assert ALEMBIC_MIGRATION_PATH.exists(), (
        f"P5-0-1a alembic 迁移文件缺失: {ALEMBIC_MIGRATION_PATH}"
    )


def test_alembic_revision_id_and_down_revision():
    """alembic 迁移 revision/down_revision 必须符合 P5-0 batch head 链。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "p5_open_005_model_extension"' in content, "revision ID 错误"
    assert (
        'down_revision = "p4_task0_lineage_extension"' in content
    ), "down_revision 必须为 P4-TASK0 末态（HEAD 基线）"


def test_alembic_migration_uses_idempotent_type_creation():
    """迁移必须使用 create_type=False + checkfirst=True 幂等保护（PG enum 不可逆）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    # 1 个新 enum：relief_scenario_enum
    assert 'name="relief_scenario_enum"' in content, "迁移缺 relief_scenario_enum 定义"
    assert "create_type=False" in content, "迁移必须用 create_type=False 防重复创建"
    assert "checkfirst=True" in content, "迁移必须用 checkfirst=True 幂等保护"
    # DROP IF EXISTS 保护（downgrade 也幂等）
    assert "DROP TYPE IF EXISTS relief_scenario_enum" in content, (
        "downgrade 必须用 DROP TYPE IF EXISTS 防已删除时崩溃"
    )


def test_alembic_migration_creates_3_tables():
    """迁移必须 CREATE TABLE relief_results / column_sizing / mixer_results。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    for table in ("relief_results", "column_sizing", "mixer_results"):
        assert f'create_table(\n        "{table}"' in content, (
            f"迁移缺 CREATE TABLE {table}"
        )


# ============================================================================
# 7. RECORD_TYPE_REGISTRY 8 类（5 既有 + 3 新增）
# ============================================================================


def test_record_type_registry_has_8_entries():
    """RECORD_TYPE_REGISTRY 必须 8 类（5 既有 + 3 新增）。"""
    assert len(RECORD_TYPE_REGISTRY) == 8, (
        f"RECORD_TYPE_REGISTRY 应有 8 类，实际 {len(RECORD_TYPE_REGISTRY)}: "
        f"{list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_contains_p5_0_1a_3_classes():
    """RECORD_TYPE_REGISTRY 必须含 P5-0-1a 新增 3 类。"""
    missing = P5_0_1A_REGISTRY_KEYS - frozenset(RECORD_TYPE_REGISTRY.keys())
    assert not missing, f"REGISTRY 缺 P5-0-1a 类: {missing}"


def test_record_type_registry_preserves_legacy_5_classes():
    """REGISTRY 必须保留 P4-TASK0 闭环的 5 既有类（防回归）。"""
    missing = LEGACY_REGISTRY_KEYS - frozenset(RECORD_TYPE_REGISTRY.keys())
    assert not missing, f"REGISTRY 缺既有类（防回归）: {missing}"


def test_record_type_registry_p5_0_1a_classes_point_to_orm():
    """新增 3 类的 registry 值必须指向新 ORM 类（防 import aliasing 错误）。"""
    assert RECORD_TYPE_REGISTRY["ReliefResult"] is ReliefResult
    assert RECORD_TYPE_REGISTRY["ColumnSizingResult"] is ColumnSizingResult
    assert RECORD_TYPE_REGISTRY["MixerResult"] is MixerResult
