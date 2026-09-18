"""P5-4 HEAT: duty 双轨字段（duty_legacy + duty_calc）contract 测试。

按 ADR-0027 V1.0 决策 5 跟踪项 — 2026-09-18 P5-4 实施闭环：

**覆盖**：
1. HeatResult ORM 字段含 duty_legacy + duty_calc + 原 duty（向后兼容）
2. duty_legacy 与 duty_calc 均为 Float nullable（语义：上游 P4 vs P5 计算）
3. alembic 迁移 p5_4_heat_duty_split 加 2 列 + 回填 duty_calc
4. 迁移可降级（downgrade 写回 duty → drop 列）
"""
from __future__ import annotations

from pathlib import Path

from app.models.calc import HeatResult

# ============================================================================
# 1. HeatResult ORM 字段
# ============================================================================


def test_heat_result_has_duty_legacy_column():
    """duty_legacy 列必须存在（Float nullable，P4 上游 duty）。"""
    cols = frozenset(c.name for c in HeatResult.__table__.columns)
    assert "duty_legacy" in cols, f"HeatResult 缺 duty_legacy: {cols}"


def test_heat_result_has_duty_calc_column():
    """duty_calc 列必须存在（Float nullable，P5 计算 duty）。"""
    cols = frozenset(c.name for c in HeatResult.__table__.columns)
    assert "duty_calc" in cols, f"HeatResult 缺 duty_calc: {cols}"


def test_heat_result_keeps_legacy_duty_column():
    """原 `duty` 列必须保留（向后兼容 P5-OPEN-006 §"9 旧标量"承诺）。"""
    cols = frozenset(c.name for c in HeatResult.__table__.columns)
    assert "duty" in cols, f"HeatResult 缺 duty（向后兼容）: {cols}"


def test_duty_legacy_is_float_nullable():
    """duty_legacy 类型 = Float，nullable=True（语义：溯源未知可空）。"""
    col = HeatResult.__table__.columns["duty_legacy"]
    assert "FLOAT" in str(col.type).upper(), f"duty_legacy 类型错: {col.type}"
    assert col.nullable is True, f"duty_legacy 必须 nullable=True: {col.nullable}"


def test_duty_calc_is_float_nullable():
    """duty_calc 类型 = Float，nullable=True。"""
    col = HeatResult.__table__.columns["duty_calc"]
    assert "FLOAT" in str(col.type).upper(), f"duty_calc 类型错: {col.type}"
    assert col.nullable is True, f"duty_calc 必须 nullable=True: {col.nullable}"


# ============================================================================
# 2. alembic 迁移 p5_4_heat_duty_split
# ============================================================================


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "p5_4_heat_duty_split.py"
    )


def test_alembic_migration_file_exists():
    path = _migration_path()
    assert path.exists(), f"P5-4 duty split alembic 迁移文件缺失: {path}"


def test_alembic_revision_and_down_revision():
    """revision = p5_4_heat_duty_split，down_revision = p4_4_sim_import_preview_towers。"""
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    assert 'revision = "p5_4_heat_duty_split"' in content
    assert 'down_revision = "p4_4_sim_import_preview_towers"' in content, (
        "down_revision 必须为 p3.2-sim 分支 head (p4_4_sim_import_preview_towers)"
    )


def test_alembic_migration_adds_two_duty_columns():
    """upgrade 必须 op.add_column × 2（duty_legacy + duty_calc）+ 回填 duty_calc。"""
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    assert 'sa.Column("duty_legacy"' in content, "缺 duty_legacy 列定义"
    assert 'sa.Column("duty_calc"' in content, "缺 duty_calc 列定义"
    # backfill: existing duty → duty_calc
    assert "UPDATE heat_results SET duty_calc = duty" in content, (
        "缺存量回填 SQL（duty → duty_calc）"
    )


def test_alembic_migration_is_reversible():
    """downgrade 必须先回填 duty（COALESCE）→ 再 drop 两列。"""
    path = _migration_path()
    content = path.read_text(encoding="utf-8")
    # downgrade 顺序：先 UPDATE 回填 duty → 再 drop duty_calc → drop duty_legacy
    assert "COALESCE(duty_legacy, duty_calc)" in content, (
        "downgrade 必须用 COALESCE 写回 duty（保数据）"
    )
    # drop_column 调用两次（按逆序：先 duty_calc 后 duty_legacy）
    assert content.count("op.drop_column") == 2, "downgrade 缺 drop_column × 2"