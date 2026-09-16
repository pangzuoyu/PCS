"""P5-0-5 Task 24a: PSV 多标准配置 + 9 类 registry contract 测试。

按 SUP-P5-PSV-001 §3 + ADR-0028 V1.1（决策 10a G1-G6 门禁 + 决策 11 GB 分层阈值）：

**本测试覆盖**：
1. 新表 `project_calculation_standard_profiles` ORM 13 字段齐全
2. DisciplineEnum / StandardProfileCodeEnum 6/3 值
3. 3 CHECK 约束：discipline_enum / profile_code_enum / custom_requires_approval
   （future_dated_forbidden 下沉 API 层 Pydantic 校验）
4. EXCLUDE USING gist 约束 `project_standard_default_unique`（区间相交）
5. 2 部分索引：current_default + migrated_default
6. psv_results 加 7 列 + override_paired_chk + 2 部分索引
7. relief_results 加 7 列 + override_paired_chk + 2 部分索引
8. RECORD_TYPE_REGISTRY == 9（Q4 约束）
9. alembic migration 链 p5_0_4a_pk_rename_and_tag_number → p5_0_5_psv_multi_standard
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import Index

from app.models.calc import PsvResult, ReliefResult
from app.models.psv_standards import (
    DisciplineEnum,
    ProjectCalculationStandardProfile,
    StandardProfileCodeEnum,
)
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_MIGRATION_PATH = (
    ROOT / "alembic" / "versions" / "p5_0_5_psv_multi_standard.py"
)

# 13 业务字段（DICT V3.3 不含此表，本测试固化 SUP-P5-PSV-001 §3.1 字段）
PCS_FIELDS: frozenset[str] = frozenset({
    "id",
    "project_id",
    "discipline",
    "profile_code",
    "standard_refs_json",
    "approval_json",
    "is_default",
    "migrated_default",
    "effective_from",
    "effective_to",
    "approved_by",
    "created_at",
    "updated_at",
})

# psv_results / relief_results 加的 7 列
STANDARD_7_COLUMNS: frozenset[str] = frozenset({
    "standard_profile_code",
    "standard_refs_json",
    "formula_ref_json",
    "pending_review",
    "migrated_default",
    "override_reason",
    "override_approval_json",
})


# ============================================================================
# 1. ORM 字段
# ============================================================================


def test_project_calculation_standard_profile_tablename():
    assert ProjectCalculationStandardProfile.__tablename__ == (
        "project_calculation_standard_profiles"
    )


def test_project_calculation_standard_profile_has_13_fields():
    cols = frozenset(ProjectCalculationStandardProfile.__table__.columns.keys())
    assert PCS_FIELDS <= cols, f"ProjectCalculationStandardProfile 缺字段: {PCS_FIELDS - cols}"


def test_psv_result_has_7_new_columns():
    cols = frozenset(PsvResult.__table__.columns.keys())
    assert STANDARD_7_COLUMNS <= cols, (
        f"psv_results 缺标准配置 7 列: {STANDARD_7_COLUMNS - cols}"
    )


def test_relief_result_has_7_new_columns():
    cols = frozenset(ReliefResult.__table__.columns.keys())
    assert STANDARD_7_COLUMNS <= cols, (
        f"relief_results 缺标准配置 7 列: {STANDARD_7_COLUMNS - cols}"
    )


# ============================================================================
# 2. Enum 完整性
# ============================================================================


def test_discipline_enum_has_6_values():
    """DisciplineEnum: PSV / VESSEL / HEAT / PIPE / PUMP / SEPARATOR（6 类）。"""
    values = {m.value for m in DisciplineEnum}
    assert values == {"PSV", "VESSEL", "HEAT", "PIPE", "PUMP", "SEPARATOR"}, (
        f"DisciplineEnum 应 6 值，实际 {values}"
    )


def test_standard_profile_code_enum_has_3_values():
    """StandardProfileCodeEnum: API / GB / CUSTOM（3 类）。"""
    values = {m.value for m in StandardProfileCodeEnum}
    assert values == {"API", "GB", "CUSTOM"}, (
        f"StandardProfileCodeEnum 应 3 值，实际 {values}"
    )


# ============================================================================
# 3. CHECK 约束
# ============================================================================


def test_psv_results_override_paired_chk_present():
    """psv_results 必须有 override_paired_chk CHECK（reason/approval_json 成对）。"""
    check_names = {
        c.name for c in PsvResult.__table__.constraints if c.__class__.__name__ == "CheckConstraint"
    }
    assert "psv_override_paired_chk" in check_names, (
        f"psv_results 缺 psv_override_paired_chk 约束，实际 {check_names}"
    )


def test_relief_results_override_paired_chk_present():
    """relief_results 必须有 relief_override_paired_chk CHECK。"""
    check_names = {
        c.name
        for c in ReliefResult.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    }
    assert "relief_override_paired_chk" in check_names, (
        f"relief_results 缺 relief_override_paired_chk 约束，实际 {check_names}"
    )


def test_pcs_profile_has_3_check_constraints():
    """ProjectCalculationStandardProfile 必须有 3 CHECK 约束。

    future_dated_forbidden 下沉 API 层（Pydantic 校验），DB 层不强制
    跨方言不安全的 INTERVAL 表达式。
    """
    check_names = {
        c.name
        for c in ProjectCalculationStandardProfile.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    }
    expected = {
        "discipline_enum_chk",
        "profile_code_enum_chk",
        "custom_requires_approval_chk",
    }
    assert expected <= check_names, (
        f"ProjectCalculationStandardProfile 缺 CHECK: {expected - check_names}"
    )


# ============================================================================
# 4. EXCLUDE USING gist 约束（alembic migration 必须包含 DDL）
# ============================================================================


def test_alembic_migration_creates_exclude_gist_constraint():
    """alembic migration 必须用 ALTER TABLE ADD CONSTRAINT EXCLUDE USING gist 创建约束。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "EXCLUDE USING gist" in content, (
        "alembic migration 缺 EXCLUDE USING gist 约束"
    )
    assert "project_standard_default_unique" in content, (
        "alembic migration 缺约束名 project_standard_default_unique"
    )
    assert "tstzrange(" in content, (
        "alembic migration 缺 tstzrange 区间相交检测"
    )
    assert "is_default = TRUE AND migrated_default = FALSE" in content, (
        "EXCLUDE 约束 WHERE 子句必须排除迁移占位"
    )


def test_alembic_migration_creates_extension_btree_gist():
    """alembic migration 必须 CREATE EXTENSION btree_gist（EXCLUDE 约束前置依赖）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS btree_gist" in content, (
        "alembic migration 缺 CREATE EXTENSION btree_gist"
    )


# ============================================================================
# 5. 部分索引
# ============================================================================


def test_pcs_profile_has_2_partial_indexes():
    """ProjectCalculationStandardProfile 必须有 2 部分索引。"""
    indexes = [
        idx for idx in ProjectCalculationStandardProfile.__table__.indexes
        if isinstance(idx, Index) and idx.dialect_kwargs.get("postgresql_where") is not None
    ]
    index_where_clauses = [str(idx.dialect_kwargs["postgresql_where"]) for idx in indexes]
    # current_default 部分索引
    assert any(
        "is_default = TRUE" in c and "migrated_default = FALSE" in c
        for c in index_where_clauses
    ), f"缺 current_default 部分索引，actual WHERE: {index_where_clauses}"
    # migrated_default 部分索引
    assert any("migrated_default = TRUE" in c for c in index_where_clauses), (
        f"缺 migrated_default 部分索引，actual WHERE: {index_where_clauses}"
    )


def test_psv_results_has_2_partial_indexes():
    """psv_results 必须有 2 部分索引（pending_review + migrated_default）。"""
    where_clauses = [
        str(idx.dialect_kwargs.get("postgresql_where", ""))
        for idx in PsvResult.__table__.indexes
    ]
    assert any("pending_review = TRUE" in c for c in where_clauses), (
        f"psv_results 缺 pending_review 部分索引，actual: {where_clauses}"
    )
    assert any("migrated_default = TRUE" in c for c in where_clauses), (
        f"psv_results 缺 migrated_default 部分索引，actual: {where_clauses}"
    )


def test_relief_results_has_2_partial_indexes():
    """relief_results 必须有 2 部分索引（pending_review + migrated_default）。"""
    where_clauses = [
        str(idx.dialect_kwargs.get("postgresql_where", ""))
        for idx in ReliefResult.__table__.indexes
    ]
    assert any("pending_review = TRUE" in c for c in where_clauses), (
        f"relief_results 缺 pending_review 部分索引，actual: {where_clauses}"
    )
    assert any("migrated_default = TRUE" in c for c in where_clauses), (
        f"relief_results 缺 migrated_default 部分索引，actual: {where_clauses}"
    )


# ============================================================================
# 6. RECORD_TYPE_REGISTRY == 9（Q4 约束）
# ============================================================================


def test_record_type_registry_count_is_9():
    """P5-0 批约束 3（Q4）：Task 24 后 REGISTRY 必须恰好 9 类。

    8 → 9：+ ProjectCalculationStandardProfile
    防误加（不跳到 10 或 13）。
    """
    assert len(RECORD_TYPE_REGISTRY) == 9, (
        f"REGISTRY 应 9 类（Q4 约束），实际 {len(RECORD_TYPE_REGISTRY)}: "
        f"{list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_contains_pcs_profile():
    """REGISTRY 必须包含 ProjectCalculationStandardProfile（P5-0-5 新增）。"""
    assert "ProjectCalculationStandardProfile" in RECORD_TYPE_REGISTRY, (
        f"REGISTRY 缺 ProjectCalculationStandardProfile: "
        f"{list(RECORD_TYPE_REGISTRY.keys())}"
    )


def test_record_type_registry_preserves_p5_0_1a_8_classes():
    """REGISTRY 9 类必须包含 P5-0-1a 8 类（无意外删除）。"""
    expected_p5_0_1a = {
        "PipingResult",
        "PumpResult",
        "FlashResult",
        "PipeNetworkResult",
        "TwoPhaseResult",
        "ReliefResult",
        "ColumnSizingResult",
        "MixerResult",
    }
    assert expected_p5_0_1a <= set(RECORD_TYPE_REGISTRY.keys()), (
        f"REGISTRY 缺 P5-0-1a 8 类: {expected_p5_0_1a - set(RECORD_TYPE_REGISTRY.keys())}"
    )


# ============================================================================
# 7. alembic migration 链
# ============================================================================


def test_alembic_migration_file_exists():
    assert ALEMBIC_MIGRATION_PATH.exists(), (
        f"P5-0-5 alembic 迁移文件缺失: {ALEMBIC_MIGRATION_PATH}"
    )


def test_alembic_revision_and_down_revision():
    """revision = p5_0_5_psv_multi_standard，down_revision = p5_0_4a_pk_rename_and_tag_number。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "p5_0_5_psv_multi_standard"' in content
    assert (
        'down_revision = "p5_0_4a_pk_rename_and_tag_number"' in content
    ), "down_revision 必须为 P5-0-4a 末态（p5_0_4a_pk_rename_and_tag_number）"


def test_alembic_migration_creates_pcs_table():
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "project_calculation_standard_profiles" in content
    assert "CREATE TABLE" in content or "op.create_table" in content


def test_alembic_migration_adds_7_columns_to_psv_results():
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    for col in STANDARD_7_COLUMNS:
        assert col in content, f"alembic migration 缺 psv_results.{col} 列"
    assert content.count("psv_results") >= 8, (
        "psv_results 应至少 8 次引用（7 add_column + 表名）"
    )


def test_alembic_migration_adds_7_columns_to_relief_results():
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    for col in STANDARD_7_COLUMNS:
        assert col in content, f"alembic migration 缺 relief_results.{col} 列"
