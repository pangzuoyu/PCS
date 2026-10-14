"""补 `project_calculation_standard_profiles.future_dated_forbidden_chk`。

## 为什么这条现在才补（2026-10-14）

这条 CHECK **从来没有任何迁移创建过**。ORM 在
`app/models/psv_standards.py:202` 声明了它，开发库 `pcs` 上也有它 ——
但 `pcs_test` 上没有。

2026-10-07 的「`alembic check` 43 条 → 0」把这条算作「DB 有安全网、
ORM 漏声明」，于是**照着开发库补了 ORM 声明**。那只在一个库上归零：
`alembic check` 比的是 ORM ↔ **你连上的那个 schema**，不是 ORM ↔
迁移应该造出的 schema。跨库漂移根本不在它的视野里。

2026-10-14 把 `pcs_test` 对齐到 p8_007 后实测：

| 库 | `future_dated_forbidden_chk` | `alembic check` |
|---|---|---|
| `pcs`（开发） | 有 | exit 0 |
| `pcs_test` | **无** | **exit 255** |

## 为什么必须幂等

两个库的状态不同（一个有、一个没有），而迁移是一条线性链、只能往前跑。
直接 `ADD CONSTRAINT` 会在已有它的库上炸；PG 又**没有**
`ADD CONSTRAINT IF NOT EXISTS`。所以先查 `pg_constraint` 再决定。

## 表达式的形态

ORM 写的是 `effective_from <= created_at + interval '1 second'`；
开发库实际存的是 `(effective_from <= (created_at + '00:00:01'::interval))`
—— 同一件事的两种打印。**alembic 按名字匹配 CHECK，不比对表达式**
（见 CLAUDE.md / bug-147），所以这里用可读写法即可，不必抄 cast 形态。

## 单测为什么抓不到

`tests/conftest.py:74` 有一条 SQLite 改写，把这个 PG 专有的 `interval`
表达式在内存库里换掉。而单测从 ORM metadata 建表、**不跑迁移** ——
于是无论这条迁移写没写、写得对不对，4400+ 测试一律绿。
"""
from __future__ import annotations

from alembic import op

revision = "p8_008"
down_revision = "p8_007"
branch_labels = None
depends_on = None

_TABLE = "project_calculation_standard_profiles"
_CONSTRAINT = "future_dated_forbidden_chk"
_EXPR = "effective_from <= created_at + interval '1 second'"


def upgrade() -> None:
    # ⚠️ PG 没有 `ADD CONSTRAINT IF NOT EXISTS`，所以先查 pg_constraint。
    # 不能用 `if_exists=True` 之类的替代品 —— 那是 drop 的方向。
    op.execute(f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = '{_CONSTRAINT}'
        ) THEN
            ALTER TABLE {_TABLE}
                ADD CONSTRAINT {_CONSTRAINT} CHECK ({_EXPR});
        END IF;
    END $$;
    """)


def downgrade() -> None:
    # ⚠️ 不设 `if_exists`：这条约束在升级前就可能已经存在（开发库就是），
    # 无条件 drop 会把它删掉 —— 而删掉之后 ORM 仍然声明着它，
    # 于是 `alembic check` 立刻报 `add_constraint`，把 downgrade 变成
    # 「制造漂移」。用 IF EXISTS 让它在两种初始状态下都安全。
    op.execute(f"ALTER TABLE {_TABLE} DROP CONSTRAINT IF EXISTS {_CONSTRAINT};")
