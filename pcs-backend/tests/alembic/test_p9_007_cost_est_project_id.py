"""`p9_007`（cost_est_results 补 project_id）的迁移形状断言 —— P9A-5 Task B。

⚠️ 本文件只断言**迁移与 ORM 一致**（列形状 / 回填 / 约束），**不跑真库升级** ——
真库升级的验证口径见 `scripts/check_migration_idempotency.py` +
`alembic check`（每库各一次，退出码 **255**）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.models.calc import CostEstResult

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_007_cost_est_project_id.py"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_exists_and_is_chained_to_p9_006():
    """`revision = p9_007` / `down_revision = p9_006`（p9_006 是当前 head）。"""
    assert MIGRATION.exists(), "p9_007 迁移文件不存在"
    tree = ast.parse(_source())
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = ast.literal_eval(node.value)
    assert values["revision"] == "p9_007"
    assert values["down_revision"] == "p9_006", (
        f"down_revision 应为 p9_006（当前 head），实际 {values['down_revision']}"
    )


def test_orm_declares_project_id_not_null_with_fk_and_index():
    """ORM 侧：NOT NULL + FK → projects.project_id + 索引。

    ⚠️ 这三条任缺一条，`check_record_access_or_404` 或列表过滤就会出问题：
    - NOT NULL：NULL 的行在守卫里会走到 500 分支（运行期才暴露的坏数据）
    - FK：没有它，`project_id` 可以指向不存在的项目
    - index：按项目过滤是本表**唯一**的列表查询路径
    """
    col = CostEstResult.__table__.c.project_id
    assert not col.nullable
    fks = [f.target_fullname for f in col.foreign_keys]
    assert fks == ["projects.project_id"], f"FK 目标不对：{fks}"
    assert col.index is True, "project_id 缺索引（按项目过滤是主查询路径）"


def test_migration_backfills_from_equipment_list():
    """回填必须 `UPDATE ... FROM equipment_list`（**同一条 SQL**）。

    ⚠️ 不能在迁移里 import app 模型跑 ORM 查询 —— p9_006 那种「SAVEPOINT
    套 SAVEPOINT」的事务处理是另一类复杂度；这里一条 SQL 就够。
    """
    src = _source()
    assert "UPDATE cost_est_results" in src
    assert "FROM equipment_list" in src
    assert "SET project_id = e.project_id" in src


def test_migration_fails_loudly_on_unbackfillable_orphan_rows():
    """回填后仍有 NULL ⇒ **迁移显式失败**，不静默留坏数据。

    ⚠️ 留 NULL 的行在守卫里会走 `check_record_access_or_404` 的 **500**
    分支（「Record missing project_id」）—— 那是一个**运行期**才暴露、
    与本缺陷无关的报错 ⇒ 排查成本极高。⇒ 在迁移里就炸。
    """
    src = _source()
    assert "RAISE EXCEPTION" in src
    assert "cost_est_results WHERE project_id IS NULL" in src


def test_migration_does_not_add_the_columns_we_deliberately_refused():
    """**不补** workspace_id / sign_status / updated_at（P9A-5 Task B 裁决）。

    理由：该表的设计是「1:1 跟随设备、状态跟设备」；补这三列是另一套设计。
    特别地 `updated_at` 会让 ADR-0048 §⑥ 的退化阶梯对它有**两档**，而
    `TABLE_CAPABILITIES` 现在显式登记 `has_updated_at=False`。
    ⇒ 若有人「顺手补上」，退化阶梯与能力表的登记会静默不一致。
    """
    cols = set(CostEstResult.__table__.c.keys())
    for forbidden in ("workspace_id", "sign_status", "updated_at"):
        assert forbidden not in cols, (
            f"CostEstResult 不该有 {forbidden}（P9A-5 Task B 刻意不补）"
        )
    from app.services.edit_guard import TABLE_CAPABILITIES

    assert TABLE_CAPABILITIES["CostEstResult"].has_updated_at is False


@pytest.mark.parametrize("column", ["project_id"])
def test_migration_adds_exactly_one_column(column: str):
    """迁移只加一列（`add_column` 一次）。"""
    src = _source()
    assert src.count("op.add_column(") == 1
    assert f'"{column}"' in src
