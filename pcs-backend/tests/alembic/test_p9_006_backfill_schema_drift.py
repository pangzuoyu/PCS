"""p9_006 的回填必须在「ORM 比迁移先加了列」的 schema 上也能跑。

## 这条守卫为什么存在

2026-10-21：CI（`api-drift` job）在**全新库**上 `alembic upgrade head` 失败：

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn)
column cost_est_results.project_id does not exist
```

根因：`p9_006`（给 `cost_est_results` 补 `record_hash`）的回填用 **ORM 实体**
查询（`select(CostEstResult)`）⇒ SELECT 会带上 ORM 声明的**全部**列 ——
**包括 `project_id`**，而那一列由**下一个**迁移 `p9_007` 才添加
⇒ 迁移跑到自己这一半时，那一列**还不存在**。

⚠️ 这个 bug **只**在全新库上出现：dev 库在 `p9_006` 写好之前就已经应用过它
（那时 ORM 的 `CostEstResult` 还没有 `project_id`）⇒ 本仓 CLAUDE.md 说的
**「漂移盲区：单测照绿、真库会炸」**的又一例。

## 本文件钉住的性质

回填**只读此刻 DB 里已存在的列** ⇒ 任何「ORM 比迁移先加列」的写法都不会再让
全新库炸掉。

⚠️ 为什么不用「真跑一遍 alembic upgrade head」做断言：迁移链是 **PostgreSQL
方言**的（`DO $$` / `ADD CONSTRAINT` / `UUID`），本仓单测跑**内存 SQLite**
（从 ORM metadata 建表）⇒ 那条路**跑不起来**。本文件改为**直接喂给回填函数
一个「p9_006 时刻的 schema」**，把同一件事钉住且能在 CI 里跑。
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Uuid,
    create_engine,
    text,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p9_006_cost_est_record_hash.py"
)


def _load_migration_module():
    """按文件路径加载迁移模块（迁移目录不是包，不能直接 import）。"""
    spec = importlib.util.spec_from_file_location(
        "p9_006_cost_est_record_hash_migration", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def legacy_schema_engine():
    """`p9_006` 时刻的 `cost_est_results`：**没有** `project_id`。

    （`project_id` 由下一个迁移 `p9_007` 添加 —— 这正是 CI 炸掉的原因。）
    """
    engine = create_engine("sqlite://")
    meta = MetaData()
    Table(
        "cost_est_results",
        meta,
        Column("cost_est_id", Uuid, primary_key=True),
        Column("equipment_id", Uuid, nullable=False),
        Column("estimated_cost", Numeric(18, 2), nullable=False),
        Column("currency", String(10), nullable=False),
        Column("cost_index_year", Integer, nullable=False),
        Column("base_cost", Numeric(18, 2), nullable=True),
        Column("base_year", Integer, nullable=True),
        Column("cepci_index_base", Float, nullable=True),
        Column("cepci_index_target", Float, nullable=True),
        Column("correlation_source", String(64), nullable=True),
        Column("scaling_exponent", Float, nullable=True),
        Column("record_hash", String(64), nullable=False, server_default=""),
        Column("created_at", DateTime(timezone=True), nullable=True),
    )
    meta.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cost_est_results (
                    cost_est_id, equipment_id, estimated_cost, currency,
                    cost_index_year, base_cost, base_year, cepci_index_base,
                    cepci_index_target, correlation_source, scaling_exponent,
                    record_hash, created_at
                ) VALUES (
                    :cid, :eid, :cost, :cur, :year, NULL, NULL, NULL,
                    NULL, NULL, NULL, '', :created
                )
                """
            ),
            {
                # ⚠️ 用 `.hex`（32 位无横线）：`Uuid` 类型的 bind processor 就是
                # 这么写的（CHAR(32)）⇒ 带横线的 36 位字符串存进去后，
                # ORM 的 UPDATE（WHERE 用 hex）会 0 行匹配 ⇒ StaleDataError。
                "cid": uuid.uuid4().hex,
                "eid": uuid.uuid4().hex,
                "cost": 35,
                "cur": "USD",
                "year": 2019,
                "created": "2026-10-20T10:22:31",
            },
        )
    yield engine
    engine.dispose()


def test_backfill_runs_when_orm_declares_a_column_the_db_lacks(legacy_schema_engine):
    """ORM 有 `project_id`、DB 没有 ⇒ 回填仍必须跑完（不能抛 UndefinedColumn）。

    ⚠️ 这就是 CI 红灯的形状：全新库上 `alembic upgrade head` 死在这里。
    """
    module = _load_migration_module()
    with legacy_schema_engine.begin() as conn:
        n = module._backfill_record_hash(conn)
    assert n == 1


def test_backfill_fills_record_hash(legacy_schema_engine):
    """回填把 `record_hash` 从空串（未计算）填成 16 hex。"""
    module = _load_migration_module()
    with legacy_schema_engine.begin() as conn:
        module._backfill_record_hash(conn)

    with legacy_schema_engine.connect() as conn:
        value = conn.execute(
            text("SELECT record_hash FROM cost_est_results")
        ).scalar_one()
    assert value != "", "回填后不应仍是「未计算」的空串"
    assert len(value) == 16, f"record_hash 应为 16 hex，实为 {value!r}"


def test_backfill_is_idempotent(legacy_schema_engine):
    """跑两次 ⇒ 同一个 hash（`compute_record_hash` 的幂等性）。"""
    module = _load_migration_module()
    with legacy_schema_engine.begin() as conn:
        module._backfill_record_hash(conn)
    with legacy_schema_engine.connect() as conn:
        first = conn.execute(
            text("SELECT record_hash FROM cost_est_results")
        ).scalar_one()

    with legacy_schema_engine.begin() as conn:
        module._backfill_record_hash(conn)
    with legacy_schema_engine.connect() as conn:
        second = conn.execute(
            text("SELECT record_hash FROM cost_est_results")
        ).scalar_one()

    assert first == second
