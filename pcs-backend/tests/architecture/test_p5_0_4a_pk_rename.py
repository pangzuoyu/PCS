"""P5-0-4a Task 4a: PK rename + tag_number 统一 contract 测试。

P5-0-4 拆分 4a/4b（2026-09-16 用户裁决）：
- **4a（本测试覆盖）**：PK rename 10 表（*_calc_id → *_id）+ tag_number 统一
- 4b：字段平铺（SUP-001~014）— 延后 sprint

DICT V3.3 字典约定（schema_compact_dict.md §4.1）：16 张计算表 PK = `*_id`。
本测试固化 4a 改名契约，防止后续回归。

门禁：
1. ORM 10 表 PK 列名 = DICT V3.3 字典约定（移除 _calc 后缀）
2. column_sizing.tag_number 列存在（与 16 张计算表 TaggedRecordMixin.tag_number 一致）
3. alembic migration 文件存在 + revision/down_revision 正确
4. 迁移脚本使用 op.alter_column(new_column_name=) 模式
5. RECORD_TYPE_REGISTRY 计数不变（8 类 — Task 4a 不涉及新表，仅字段重命名）
6. 既有两文件（test_sup008_result_fields / test_two_phase）已同步 two_phase_id 引用（防回归）
"""
from __future__ import annotations

from pathlib import Path

from app.models.calc import (
    ColumnSizingResult,
    CoolingTowerResult,
    CvResult,
    FiltrationResult,
    HeatResult,
    OpenChannelResult,
    PsychroResult,
    RestrictionResult,
    SepEquipResult,
    TwoPhaseResult,
    VesselResult,
)
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_MIGRATION_PATH = (
    ROOT / "alembic" / "versions" / "p5_0_4a_pk_rename_and_tag_number.py"
)

# DICT V3.3 字典约定 PK 列名（schema_compact_dict.md §4.1）
DICT_V33_PK_NAMES: frozenset[str] = frozenset({
    "vessel_id",
    "two_phase_id",
    "sep_equip_id",
    "heat_exchanger_id",
    "cv_id",
    "orifice_id",
    "cooling_tower_id",
    "psychro_id",
    "open_channel_id",
    "filter_id",
})

# ORM 历史命名（移除 _calc 后缀前的 *_calc_id）
LEGACY_PK_NAMES: frozenset[str] = frozenset({
    "vessel_calc_id",
    "two_phase_calc_id",
    "sep_calc_id",
    "heat_calc_id",
    "cv_calc_id",
    "orifice_calc_id",
    "ct_calc_id",
    "psychro_calc_id",
    "channel_calc_id",
    "filter_calc_id",
})


# ============================================================================
# 1. ORM 列名（10 表 PK + column_sizing.tag_number）
# ============================================================================


def test_vessel_result_pk_is_vessel_id():
    """VesselResult PK 必须是 vessel_id（DICT V3.3）。"""
    assert "vessel_id" in VesselResult.__table__.columns.keys()
    assert "vessel_calc_id" not in VesselResult.__table__.columns.keys()


def test_two_phase_result_pk_is_two_phase_id():
    """TwoPhaseResult PK 必须是 two_phase_id（DICT V3.3）。"""
    assert "two_phase_id" in TwoPhaseResult.__table__.columns.keys()
    assert "two_phase_calc_id" not in TwoPhaseResult.__table__.columns.keys()


def test_sep_equip_result_pk_is_sep_equip_id():
    """SepEquipResult PK 必须是 sep_equip_id（DICT V3.3）。"""
    assert "sep_equip_id" in SepEquipResult.__table__.columns.keys()
    assert "sep_calc_id" not in SepEquipResult.__table__.columns.keys()


def test_heat_result_pk_is_heat_exchanger_id():
    """HeatResult PK 必须是 heat_exchanger_id（DICT V3.3）。"""
    assert "heat_exchanger_id" in HeatResult.__table__.columns.keys()
    assert "heat_calc_id" not in HeatResult.__table__.columns.keys()


def test_cv_result_pk_is_cv_id():
    """CvResult PK 必须是 cv_id（DICT V3.3）。"""
    assert "cv_id" in CvResult.__table__.columns.keys()
    assert "cv_calc_id" not in CvResult.__table__.columns.keys()


def test_restriction_result_pk_is_orifice_id():
    """RestrictionResult PK 必须是 orifice_id（DICT V3.3）。"""
    assert "orifice_id" in RestrictionResult.__table__.columns.keys()
    assert "orifice_calc_id" not in RestrictionResult.__table__.columns.keys()


def test_cooling_tower_result_pk_is_cooling_tower_id():
    """CoolingTowerResult PK 必须是 cooling_tower_id（DICT V3.3）。"""
    assert "cooling_tower_id" in CoolingTowerResult.__table__.columns.keys()
    assert "ct_calc_id" not in CoolingTowerResult.__table__.columns.keys()


def test_psychro_result_pk_is_psychro_id():
    """PsychroResult PK 必须是 psychro_id（DICT V3.3）。"""
    assert "psychro_id" in PsychroResult.__table__.columns.keys()
    assert "psychro_calc_id" not in PsychroResult.__table__.columns.keys()


def test_open_channel_result_pk_is_open_channel_id():
    """OpenChannelResult PK 必须是 open_channel_id（DICT V3.3）。"""
    assert "open_channel_id" in OpenChannelResult.__table__.columns.keys()
    assert "channel_calc_id" not in OpenChannelResult.__table__.columns.keys()


def test_filtration_result_pk_is_filter_id():
    """FiltrationResult PK 必须是 filter_id（DICT V3.3）。"""
    assert "filter_id" in FiltrationResult.__table__.columns.keys()
    assert "filter_calc_id" not in FiltrationResult.__table__.columns.keys()


def test_column_sizing_has_tag_number_not_column_tag():
    """ColumnSizingResult 业务位号列必须是 tag_number（P5-0 批约束 1，Q2 路径 A）。

    column_tag 是 P5-0-1a 临时命名，Task 4a 统一改造为 tag_number mixin 列名，
    与 16 张计算表 TaggedRecordMixin.tag_number 一致。
    """
    cols = frozenset(ColumnSizingResult.__table__.columns.keys())
    assert "tag_number" in cols, "ColumnSizingResult 必须含 tag_number 列"
    assert "column_tag" not in cols, (
        "ColumnSizingResult.column_tag 是 P5-0-1a 临时命名，Task 4a 必须移除"
    )


# ============================================================================
# 2. ORM 全集断言（10 表 PK 列名全集 == DICT V3.3 字典约定）
# ============================================================================


def test_all_10_pk_names_match_dict_v33():
    """10 表 PK 列名全集必须 == DICT V3.3 字典约定。"""
    actual_pks: set[str] = set()
    for cls in (
        VesselResult,
        TwoPhaseResult,
        SepEquipResult,
        HeatResult,
        CvResult,
        RestrictionResult,
        CoolingTowerResult,
        PsychroResult,
        OpenChannelResult,
        FiltrationResult,
    ):
        # PK 是第一个 primary_key=True 列
        for col in cls.__table__.columns:
            if col.primary_key:
                actual_pks.add(col.key)
                break
    assert actual_pks == DICT_V33_PK_NAMES, (
        f"10 表 PK 列名应 == DICT V3.3 字典约定。\n"
        f"差异: 缺 {DICT_V33_PK_NAMES - actual_pks}, 多 {actual_pks - DICT_V33_PK_NAMES}"
    )


def test_legacy_calc_id_names_fully_removed():
    """历史 *_calc_id 命名必须全部移除（10 项零容忍）。"""
    for cls in (
        VesselResult,
        TwoPhaseResult,
        SepEquipResult,
        HeatResult,
        CvResult,
        RestrictionResult,
        CoolingTowerResult,
        PsychroResult,
        OpenChannelResult,
        FiltrationResult,
    ):
        cols = frozenset(cls.__table__.columns.keys())
        legacy = cols & LEGACY_PK_NAMES
        assert not legacy, f"{cls.__name__} 含历史 *_calc_id 命名: {legacy}"


# ============================================================================
# 3. alembic 迁移契约
# ============================================================================


def test_alembic_migration_file_exists():
    """P5-0-4a alembic 迁移文件必须存在。"""
    assert ALEMBIC_MIGRATION_PATH.exists(), (
        f"P5-0-4a alembic 迁移文件缺失: {ALEMBIC_MIGRATION_PATH}"
    )


def test_alembic_revision_id_and_down_revision():
    """alembic 迁移 revision/down_revision 必须符合 P5-0 batch head 链。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "p5_0_4a_pk_rename_and_tag_number"' in content, "revision ID 错误"
    assert (
        'down_revision = "p5_open_005_model_extension"' in content
    ), "down_revision 必须为 P5-0-1a 末态（HEAD 基线）"


def test_alembic_migration_uses_alter_column_rename():
    """迁移 10 表 PK rename 必须使用 op.alter_column(new_column_name=) 模式。

    实现：循环遍历 _PK_RENAMES 列表（10 项）调用 op.alter_column(new_column_name=)。
    column_sizing.tag_number 统一不走 RENAME COLUMN（tag_number 已存在），
    改用 drop_constraint + drop_column + alter_column(nullable) + create_unique_constraint。
    """
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    # _PK_RENAMES 列表必须 10 项
    pk_renames_count = content.count('("vessel_results"')
    assert pk_renames_count == 1, (
        f"_PK_RENAMES 列表应定义一次（含 10 项），实际 {pk_renames_count} 次"
    )
    # 循环中 op.alter_column 调用使用 new_column_name= 模式
    assert "new_column_name=" in content, (
        "PK rename 必须用 new_column_name= 参数（PG RENAME COLUMN 模式）"
    )
    # 列表长度 10（防漏改）
    pk_list_match = [
        '"vessel_results", "vessel_calc_id", "vessel_id"',
        '"two_phase_results", "two_phase_calc_id", "two_phase_id"',
        '"sep_equip_results", "sep_calc_id", "sep_equip_id"',
        '"heat_results", "heat_calc_id", "heat_exchanger_id"',
        '"cv_results", "cv_calc_id", "cv_id"',
        '"restriction_results", "orifice_calc_id", "orifice_id"',
        '"cooling_tower_results", "ct_calc_id", "cooling_tower_id"',
        '"psychro_results", "psychro_calc_id", "psychro_id"',
        '"open_channel_results", "channel_calc_id", "open_channel_id"',
        '"filtration_results", "filter_calc_id", "filter_id"',
    ]
    for entry in pk_list_match:
        assert entry in content, f"_PK_RENAMES 列表缺: {entry}"


def test_alembic_migration_lists_all_10_pk_renames():
    """迁移必须列出全部 10 表 PK rename（防漏改）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    expected_pairs = [
        ("vessel_results", "vessel_calc_id", "vessel_id"),
        ("two_phase_results", "two_phase_calc_id", "two_phase_id"),
        ("sep_equip_results", "sep_calc_id", "sep_equip_id"),
        ("heat_results", "heat_calc_id", "heat_exchanger_id"),
        ("cv_results", "cv_calc_id", "cv_id"),
        ("restriction_results", "orifice_calc_id", "orifice_id"),
        ("cooling_tower_results", "ct_calc_id", "cooling_tower_id"),
        ("psychro_results", "psychro_calc_id", "psychro_id"),
        ("open_channel_results", "channel_calc_id", "open_channel_id"),
        ("filtration_results", "filter_calc_id", "filter_id"),
    ]
    for table, old, new in expected_pairs:
        assert f'"{table}", "{old}", "{new}"' in content, (
            f"迁移缺 PK rename: {table}.{old} → {new}"
        )


def test_alembic_migration_drops_column_sizing_column_tag():
    """迁移必须 drop column_sizing.column_tag（业务字段删除路径）。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'op.drop_column("column_sizing", "column_tag")' in content, (
        "迁移缺 op.drop_column('column_sizing', 'column_tag')"
    )


def test_alembic_migration_alter_tag_number_not_null():
    """迁移必须把 column_sizing.tag_number 提升为 NOT NULL。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    # op.alter_column 跨行调用（ruff 格式化后），断言关键字段名 + nullable=False
    assert '"column_sizing"' in content, "迁移缺 column_sizing 表引用"
    assert '"tag_number"' in content, "迁移缺 tag_number 列引用"
    assert "nullable=False" in content, "迁移缺 nullable=False 参数"
    # upgrade 和 downgrade 中应各出现一次 alter_column for tag_number
    assert content.count("op.alter_column(") >= 2, (
        "迁移应至少 2 次 op.alter_column 调用（upgrade + downgrade 各一次 tag_number）"
    )


def test_alembic_migration_unique_constraint_rehomed_on_tag_number():
    """迁移必须把 UNIQUE 约束从 column_tag 改到 tag_number。"""
    content = ALEMBIC_MIGRATION_PATH.read_text(encoding="utf-8")
    # drop uq_column_sizing_tag
    assert (
        'op.drop_constraint("uq_column_sizing_tag", "column_sizing"' in content
    ), "迁移缺 drop_constraint('uq_column_sizing_tag', ...)"
    # create UNIQUE(project_id, tag_number) 约束
    assert '"project_id", "tag_number"' in content, (
        "迁移缺 UNIQUE(project_id, tag_number) 重建"
    )


# ============================================================================
# 4. RECORD_TYPE_REGISTRY 不变（8 类）
# ============================================================================


def test_record_type_registry_still_8_entries():
    """Task 4a 不涉及新表，REGISTRY 仍 8 类。"""
    assert len(RECORD_TYPE_REGISTRY) == 8, (
        f"REGISTRY 应 8 类，实际 {len(RECORD_TYPE_REGISTRY)}: "
        f"{list(RECORD_TYPE_REGISTRY.keys())}"
    )


# ============================================================================
# 5. 既有两文件已同步 two_phase_id 引用（防回归）
# ============================================================================


def test_test_sup008_uses_two_phase_id():
    """test_sup008_result_fields.py 必须使用 two_phase_id（防回归 *_calc_id）。"""
    path = ROOT / "tests" / "models" / "test_sup008_result_fields.py"
    content = path.read_text(encoding="utf-8")
    assert "two_phase_id" in content, "test_sup008 未同步到 two_phase_id"
    assert "two_phase_calc_id" not in content, (
        "test_sup008 仍残留 two_phase_calc_id 引用（防回归失败）"
    )


def test_test_two_phase_pipe_uses_two_phase_id():
    """test_two_phase.py 必须使用 two_phase_id（防回归 *_calc_id）。"""
    path = ROOT / "tests" / "services" / "pipe" / "test_two_phase.py"
    content = path.read_text(encoding="utf-8")
    assert "two_phase_id" in content, "test_two_phase 未同步到 two_phase_id"
    assert "two_phase_calc_id" not in content, (
        "test_two_phase 仍残留 two_phase_calc_id 引用（防回归失败）"
    )


def test_test_lineage_extension_uses_two_phase_id():
    """test_lineage_extension.py 必须使用 two_phase_id（防回归 *_calc_id）。"""
    path = ROOT / "tests" / "services" / "test_lineage_extension.py"
    content = path.read_text(encoding="utf-8")
    assert "two_phase_id" in content, "test_lineage_extension 未同步到 two_phase_id"
    assert "two_phase_calc_id" not in content, (
        "test_lineage_extension 仍残留 two_phase_calc_id 引用（防回归失败）"
    )
