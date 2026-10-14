"""把两条含可空 `project_id` 的唯一约束改成 `NULLS NOT DISTINCT`（p8_009）。

## 为什么这条必要（评审 P2 #14）

`project_id` 可空表示**公司级作用域**（无项目归属的定义/样式）。
而 Postgres 认为 **NULL 互不相等** ⇒ `UNIQUE (project_id, name)` 对公司级行
**完全不起作用**：

    INSERT (project_id=NULL, name='泵数据表')   -- 通过
    INSERT (project_id=NULL, name='泵数据表')   -- 也通过，约束形同虚设

应用层唯一的防线是 `definition_service._reject_duplicate` /
`style_service.create` 里「先查有没有」—— 而那个查询**无锁**，
两个并发请求都查到「没有」，于是各自插入。

`report_styles` 那条更严重：它同时是「至多一个 ACTIVE 公司样式」这个
不变量的**唯一**数据库依据，而那个不变量原先只在应用层保证（评审 #23）。

## 为什么必须 drop + add 而不是 ALTER

PG 没有「修改约束」的操作。要让一条已有 UNIQUE 变成 NULLS NOT DISTINCT，
只能 `DROP CONSTRAINT` 再 `ADD CONSTRAINT ... UNIQUE NULLS NOT DISTINCT`。

⚠️ 这是**破坏性**的：加约束前若已有重复行，`ADD` 会直接失败。
迁移 docstring 里不该写「假设没有重复」—— 所以本迁移**不**假装会处理，
而是把它写在这里，并在升级前给出可执行的核对查询。

2026-10-14 升级前实测两个库都**无**重复（见 commit b05a56f 之后的手工核对）：

    -- report_definitions
    SELECT name, count(*) FROM report_definitions
     WHERE project_id IS NULL GROUP BY name HAVING count(*) > 1;   -- 0 行
    -- report_styles
    SELECT report_type, version, count(*) FROM report_styles
     WHERE project_id IS NULL GROUP BY 1, 2 HAVING count(*) > 1;  -- 0 行

## 幂等性

两个库的当前状态不同（都可能已改过、也可能没有），而迁移是线性链。
PG **没有** `ADD CONSTRAINT IF NOT EXISTS`，所以走 `pg_constraint` 查询。

## 单测为什么抓不到

单测从 ORM metadata 建表（不跑迁移），且 `postgresql_nulls_not_distinct`
是 **dialect 专属**选项，在 SQLite 上被忽略。所以「行为变对了」这件事
只能靠真库复核 —— `tests/services/report/test_nulls_distinct_unique.py`
只能验 ORM 确实声明了它。
"""
from __future__ import annotations

from alembic import op

revision = "p8_009"
down_revision = "p8_008"
branch_labels = None
depends_on = None

#: `(表, 约束名, 列清单)`
_TARGETS = [
    ("report_styles", "uq_report_styles_scope_version",
     "report_type, project_id, version"),
    ("report_definitions", "uq_report_definitions_project_name",
     "project_id, name"),
]


def upgrade() -> None:
    for table, name, cols in _TARGETS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name};")
        op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{name}'
            ) THEN
                ALTER TABLE {table} ADD CONSTRAINT {name}
                    UNIQUE NULLS NOT DISTINCT ({cols});
            END IF;
        END $$;
        """)


def downgrade() -> None:
    for table, name, cols in _TARGETS:
        # ⚠️ 不能无条件 ADD：降级时该约束可能**已经**是 NULLS NOT DISTINCT
        # （被手工修过、或升级跑了两遍）。无条件 ADD 会因为重名而报错，
        # 把 downgrade 变成「制造故障」。
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name};")
        op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{name}'
            ) THEN
                ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE ({cols});
            END IF;
        END $$;
        """)
