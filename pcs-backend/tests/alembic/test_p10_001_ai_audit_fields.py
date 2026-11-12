"""`p10_001`（ai_audit_log 加 P10 请求审计列）的迁移形状断言 —— P10-A Task T7。

⚠️ 本文件只断言**迁移与 ORM 一致**（列形状 / 索引形状），
**不跑真库升级** —— 真库升级的验证口径见
`scripts/check_migration_idempotency.py` + `alembic check`
（**每库各一次，独立进程**，退出码 **255** 表示有漂移）。

## 三条容易写错的

1. **时间列复用既有 `occurred_at`**（偏离登记 D16）—— 既有表已有 `occurred_at`
   ⇒ 再加一个 `timestamp` 就是**两个语义重叠的时间列** ⇒ 以后没人知道
   该读哪个 ⇒ 本迁移加 **8** 列（不是 9）。
2. **唯一索引必须是 partial**（`WHERE request_id IS NOT NULL`）——
   既有 SUP-006 行的 `request_id` 为 NULL ⇒ 非 partial 的唯一索引在 PG 上
   会因**重复 NULL** 直接失败。
3. **`op.create_index` 必须带 `if_not_exists=True`** ——
   `scripts/check_migration_idempotency.py` 的规则（`op.add_column` 不检查，
   因为 PG 不支持 `IF NOT EXISTS`）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app.models.system import AiAuditLog

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "p10_001_ai_audit_request_fields.py"
)

#: 本迁移新增的 8 列（列名 → 期望长度）。
NEW_COLUMNS: dict[str, int | None] = {
    "request_id": 64,
    "client_request_id": 128,
    "endpoint": 200,
    "status_code": None,
    "duration_ms": None,
    "sanitized_request_hash": 80,
    "response_summary": None,
    "model_version": 50,
}


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_exists_and_is_chained_to_p9_015() -> None:
    """`revision = p10_001` / `down_revision = p9_015`（p9_015 是当前 head）。"""
    assert MIGRATION.exists(), "p10_001 迁移文件不存在"
    tree = ast.parse(_source())
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = ast.literal_eval(node.value)
    assert values["revision"] == "p10_001"
    assert values["down_revision"] == "p9_015", (
        f"down_revision 应为 p9_015（当前 head），实际 {values['down_revision']}"
    )


def test_migration_adds_the_eight_columns() -> None:
    """迁移 upgrade 后 ai_audit_log 有这 8 个新列。

    ⚠️ **不含 `timestamp`** —— 时间列**复用既有 `occurred_at`**（偏离 D16）：
    两个语义重叠的时间列 ⇒ 以后没人知道该读哪个。
    """
    src = _source()
    assert src.count("op.add_column(") == len(NEW_COLUMNS), (
        f"应恰好加 {len(NEW_COLUMNS)} 列，实际 {src.count('op.add_column(')}"
    )
    for name in NEW_COLUMNS:
        assert f'"{name}"' in src, f"迁移里没有 {name} 列"
    assert '"timestamp"' not in src, (
        "不该新增 timestamp 列 —— 时间列复用既有 occurred_at（偏离登记 D16）"
    )


def test_migration_columns_are_all_nullable() -> None:
    """8 列**全部 nullable** —— 既有 SUP-006 行没有这些值。

    ⚠️ NOT NULL + 无默认值 ⇒ 迁移在存量表上直接失败。
    """
    src = _source()
    assert src.count("nullable=True") == len(NEW_COLUMNS), (
        "8 列都要 nullable=True（既有行的这些列没有值）"
    )
    assert "nullable=False" not in src


def test_request_id_unique_index_is_partial() -> None:
    """唯一索引是 partial（`WHERE request_id IS NOT NULL`）。

    ⚠️ **既有 SUP-006 行 `request_id` 为 NULL** ⇒ 非 partial 会因重复 NULL 失败。
    """
    src = _source()
    assert "ux_ai_audit_log_request_id" in src
    assert "unique=True" in src
    assert "request_id IS NOT NULL" in src


def test_create_index_uses_if_not_exists() -> None:
    """⚠️ `op.create_index` **必须**带 `if_not_exists=True`
    —— `scripts/check_migration_idempotency.py` 的规则。

    ⚠️ 按**调用块**逐个查（不能数全文出现次数 —— docstring 里也出现了这个词）。
    """
    src = _source()
    blocks = re.findall(r"op\.create_index\(.*?\n    \)", src, re.S)
    assert blocks, "迁移里没有 op.create_index"
    for block in blocks:
        assert "if_not_exists=True" in block, f"缺 if_not_exists=True：{block}"


def test_orm_matches_migration() -> None:
    """ORM 声明的列与迁移一致（漂移守卫）。

    ⚠️ 本仓的「漂移盲区」：改了迁移没同步 ORM ⇒ 单测照绿、真库会炸。
    """
    columns = AiAuditLog.__table__.c
    for name, length in NEW_COLUMNS.items():
        assert name in columns, f"ORM 少了 {name} 列"
        col = columns[name]
        assert col.nullable, f"{name} 必须 nullable（既有行没有值）"
        if length is not None:
            assert getattr(col.type, "length", None) == length, (
                f"{name} 的长度应为 {length}，实际 {getattr(col.type, 'length', None)}"
            )


def test_orm_declares_the_partial_unique_index() -> None:
    """ORM 侧也声明 partial 唯一索引 ⇒ `alembic check` 不报漂移。"""
    indexes = {idx.name: idx for idx in AiAuditLog.__table__.indexes}
    assert "ux_ai_audit_log_request_id" in indexes, list(indexes)
    idx = indexes["ux_ai_audit_log_request_id"]
    assert idx.unique is True
    assert [c.name for c in idx.columns] == ["request_id"]
    where = idx.dialect_options["postgresql"]["where"]
    assert where is not None, "唯一索引必须是 partial（postgresql_where）"
    assert "request_id IS NOT NULL" in str(where)


def test_orm_does_not_declare_a_timestamp_column() -> None:
    """ORM 侧同样**不新增** `timestamp`（偏离 D16 的另一半）。"""
    assert "timestamp" not in AiAuditLog.__table__.c
    assert "occurred_at" in AiAuditLog.__table__.c
