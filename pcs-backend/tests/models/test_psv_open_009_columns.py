"""P6-OPEN-009 fix：psv_results 补 3 列存在性 + ORM 字段断言。

ticket 091500e — PsvResult alembic drift 缺 3 列：

- stale_resolution_path（Text，可空；stale 决策链 JSON）
- hash_changed（Boolean NOT NULL default FALSE；record_hash 变更标记）
- changed_fields（JSONB，可空；变更字段清单）

本测试只校验 ORM 字段补齐（不连 DB）；DB schema 校验见 alembic roundtrip。
"""
from __future__ import annotations

from sqlalchemy import inspect

from app.models.calc import PsvResult

_PSV_OPEN_009_COLUMNS = (
    "stale_resolution_path",
    "hash_changed",
    "changed_fields",
)


def _orm_columns(model):
    """通过 SQLAlchemy Table 反射读取 ORM 字段名集合。"""
    return {c.key for c in inspect(model).columns}


def test_psv_result_has_stale_resolution_path_column() -> None:
    """PsvResult 必须含 stale_resolution_path 字段（Text，可空）。"""
    cols = _orm_columns(PsvResult)
    assert "stale_resolution_path" in cols, (
        f"PsvResult 缺 stale_resolution_path 列：{sorted(cols)}"
    )


def test_psv_result_has_hash_changed_column() -> None:
    """PsvResult 必须含 hash_changed 字段（Boolean，NOT NULL default FALSE）。"""
    cols = _orm_columns(PsvResult)
    assert "hash_changed" in cols, f"PsvResult 缺 hash_changed 列：{sorted(cols)}"


def test_psv_result_has_changed_fields_column() -> None:
    """PsvResult 必须含 changed_fields 字段（JSONB，可空）。"""
    cols = _orm_columns(PsvResult)
    assert "changed_fields" in cols, f"PsvResult 缺 changed_fields 列：{sorted(cols)}"


def test_psv_result_open_009_all_three_columns_present() -> None:
    """PsvResult OPEN-009 三列一次性校验（聚合断言，便于后续 CI 报警）。

    校验 3 列同时存在；缺失任一即 FAIL——避免单测通过但迁移不完整的回归。
    """
    cols = _orm_columns(PsvResult)
    missing = set(_PSV_OPEN_009_COLUMNS) - cols
    assert not missing, f"PsvResult OPEN-009 缺列：{missing}"