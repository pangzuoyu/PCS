"""`report_styles` 的「每个作用域至多一个 ACTIVE」下沉为数据库不变量（p8_010）。

## 为什么这条必要（用户 2026-10-14 裁决 #23）

`create` / `revise` / `activate` 都是「**先查**当前 ACTIVE，**再**决定是否报错」。

    active = (await db.execute(select(ReportStyleRow).where(
        ...scope..., ReportStyleRow.status == "ACTIVE"))).scalar_one_or_none()
    if active is not None:
        raise PcsError("该作用域已有 ACTIVE 样式")

那个 `select` **无锁**。两个并发请求都查到「没有」，于是各自插入 ——
`style_service` 的 docstring 声明为绝对的不变量，只在调用方不重叠时成立。

## 为什么用部分唯一索引而不是 `SELECT ... FOR UPDATE`

裁决理由：**部分唯一索引是永久防护，比「每次改代码都记得加锁」可靠**。
且 `revise` 与 `activate` 两条路径一次覆盖，不必在两条路径上各写一遍加锁逻辑。

另外这张表存的是**合规产物**（样式配置），跨审计写的路径上持行锁
比一个索引的代价大得多。

## 为什么必须 `NULLS NOT DISTINCT`

公司级样式的 `project_id IS NULL`，而 PG 认为 **NULL 互不相等** ——
不加它，公司级的 ACTIVE 唯一性**形同虚设**（与 p8_009 同源问题）。
PG 18 已支持该语法，实测确认。

## 升级前必须核对

加索引前若同一作用域已有两个 ACTIVE，`CREATE UNIQUE INDEX` 会**直接失败**。
本迁移**不**假装会处理，写下可执行的核对查询：

    SELECT coalesce(project_id::text,'COMPANY') AS scope, report_type, count(*)
      FROM report_styles WHERE status = 'ACTIVE'
     GROUP BY 1,2 HAVING count(*) > 1;   -- 必须 0 行

2026-10-14 实测两个库均为 0 行（开发库仅 2 行样式，其中 1 个 ACTIVE）。

## 单测为什么抓不到

`postgresql_where` 与 `postgresql_nulls_not_distinct` 都是 dialect 专属，
SQLite 上被忽略，而单测跑的正是 SQLite。行为验证只能在真库做。
`tests/api/v1/test_report_styles_active_invariant.py` 只验 ORM 声明。
"""
from __future__ import annotations

from alembic import op

revision = "p8_010"
down_revision = "p8_009"
branch_labels = None
depends_on = None

_INDEX = "uq_report_styles_one_active"


def upgrade() -> None:
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_INDEX} "
        "ON report_styles (report_type, project_id) NULLS NOT DISTINCT "
        "WHERE status = 'ACTIVE';"
    )


def downgrade() -> None:
    # ⚠️ 不用 `CREATE INDEX IF NOT EXISTS` 的反面：`DROP INDEX IF EXISTS`
    # 是安全的 —— 索引不存在时什么也不做，而**不存在**才是这里想要的状态。
    op.execute(f"DROP INDEX IF EXISTS {_INDEX};")
