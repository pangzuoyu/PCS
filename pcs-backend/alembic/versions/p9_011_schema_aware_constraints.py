"""把 6 条约束**按 schema** 补齐（TODO-088）。

## 为什么需要这条（根因）

`p8_001` / `p8_008` / `p8_009` / `p8_011` 里那几条约束的**幂等检查**写的是：

```sql
SELECT 1 FROM pg_constraint WHERE conname = '<名字>'
```

⇒ **只按名字查，不分 schema** ⇒ 而 `pg_constraint` 是**每库**不是**每 schema**
⇒ 同一个库里**别的 schema**（例如 `public`）已有同名列 ⇒ **跳过建约束**
⇒ ⇒ **本 schema 永远拿不到这条约束**。

⇒ 后果分两种：

1. **隔离 schema 验证**（本地按 CLAUDE.md 的纪律用
   `options=-csearch_path=<schema>` 建一个干净 schema 验迁移）⇒ 那个 schema 上
   `alembic check` 报 6 条**假漂移**（`add_constraint`：ORM 要、DB 没有）⇒
   **看起来**像 ORM↔迁移漂移 ⇒ 而真·全新**数据库**（CI 的 fresh Postgres）
   里没有别的 schema ⇒ 约束**会**建出来 ⇒ CI 不受影响；
2. ⚠️ **任何「按 schema 部署」的库**（多租户/影子 schema）⇒ 约束缺失 ⇒
   DB 层的安全网在那些 schema 上**根本没装**。

## 为什么用**新迁移**而不是改 p8 那几条

改**已应用**的迁移 ⇒ 已跑过的库不会重跑（内容变了但 revision 没变 ⇒ 历史与
文件不一致 ⇒ 以后重放会得到不同结果）⇒ ⇒ 用一条**新迁移**补齐 ⇒
**不改历史**。

## 为什么判据是「**当前 schema** 有没有」

补齐的目标 = 让**当前 schema** 与 ORM 声明一致 ⇒ 判据必须**分 schema**
⇒ 用 `connamespace = current_schema()::regnamespace`（PG 的
`current_schema()` 返回当前 schema 的名字）。

⇒ 已有的 schema（开发库 `pcs` / `pcs_test`）⇒ **全部跳过**（幂等）；
⇒ 缺约束的 schema（隔离 schema / 影子 schema）⇒ **补上**。

## 六条约束

| 约束 | 表 | 定义来源 |
|---|---|---|
| `uq_report_styles_scope_version` | `report_styles` | `p8_009`（NULLS NOT DISTINCT） |
| `uq_report_definitions_project_name` | `report_definitions` | `p8_009`（NULLS NOT DISTINCT） |
| `future_dated_forbidden_chk` | `project_calculation_standard_profiles` | `p8_008` |
| `ck_streams_phase` | `streams` | `p8_011`（取值来自 `StreamPhase` 枚举） |
| `ck_streams_data_mode` | `streams` | `p8_011`（取值来自 `StreamDataMode` 枚举） |
| `ck_streams_source_type` | `streams` | `p8_011`（取值来自 `StreamSourceType` 枚举） |

⚠️ 三条 `ck_streams_*` 的取值**直接引用 ORM 枚举**（`app/models/enums.py` 是
唯一来源）—— 硬编码一份就是 bug-187~191 那一族的「两份定义」。

## Revision

`revision = p9_011`，`down_revision = p9_010`（当前 head）。
"""
from __future__ import annotations

from alembic import op

revision = "p9_011"
down_revision = "p9_010"
branch_labels = None
depends_on = None

#: `(表, 约束名, 定义 SQL)` —— UNIQUE / CHECK 各自的 ADD 语句。
_STATIC_TARGETS: list[tuple[str, str, str]] = [
    (
        "report_styles",
        "uq_report_styles_scope_version",
        "UNIQUE NULLS NOT DISTINCT (report_type, project_id, version)",
    ),
    (
        "report_definitions",
        "uq_report_definitions_project_name",
        "UNIQUE NULLS NOT DISTINCT (project_id, name)",
    ),
    (
        "project_calculation_standard_profiles",
        "future_dated_forbidden_chk",
        "CHECK (effective_from <= created_at + interval '1 second')",
    ),
]

_STREAMS_TABLE = "streams"


def _stream_check_targets() -> list[tuple[str, str, str]]:
    """三条 `ck_streams_*`（取值**直接引用 ORM 枚举** ⇒ 不会与契约漂移）。"""
    from app.models.enums import StreamDataMode, StreamPhase, StreamSourceType

    specs = [
        ("phase", tuple(sorted(p.value for p in StreamPhase))),
        ("data_mode", tuple(sorted(p.value for p in StreamDataMode))),
        ("source_type", tuple(sorted(t.value for t in StreamSourceType))),
    ]
    return [
        (
            _STREAMS_TABLE,
            f"ck_streams_{col}",
            f"CHECK ({col} IS NULL OR {col} IN ({', '.join(repr(v) for v in values)}))",
        )
        for col, values in specs
    ]


def _add_if_missing(table: str, name: str, definition: str) -> None:
    """**当前 schema** 里没有这条约束 ⇒ 补上（有了就跳过 ⇒ 幂等）。"""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{name}'
                  AND connamespace = current_schema()::regnamespace
            ) THEN
                ALTER TABLE {table} ADD CONSTRAINT {name} {definition};
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """按 schema 补齐 6 条约束（已有的跳过）。"""
    for table, name, definition in _STATIC_TARGETS + _stream_check_targets():
        _add_if_missing(table, name, definition)


def downgrade() -> None:
    """删掉这 6 条约束（**只删当前 schema 里的**）。

    ⚠️ 降级会**真的**移除 DB 层的保护（CHECK / UNIQUE）⇒ 降级后应用层仍会
    校验，但「直接 SQL 写入」不再被拦 ⇒ 这是降级的固有代价，不在降级路径里修。
    """
    for table, name, _definition in _STATIC_TARGETS + _stream_check_targets():
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name};")
