"""公司级（`project_id IS NULL`）的唯一约束必须在 PG 上真的生效。

## 缺陷（评审 P2 #14）

`report_definitions` 有 `UNIQUE (project_id, name)`、
`report_styles` 有 `UNIQUE (report_type, project_id, version)`，
而 `project_id` 是**可空**的（公司级作用域）。Postgres 认为 **NULL 互不相等**，
于是公司级行完全绕开约束：两个 `project_id IS NULL` 且同名的定义可以共存，
尽管 `builder_service` 把「没有 project_id」当作公司级模板作用域。

两个并发请求还能各自通过「先查有没有」的检查（那检查无锁），
于是产生**两个同版本的 ACTIVE 公司样式**。

## ⚠️ 这个约束 SQLite 测不出来

`postgresql_nulls_not_distinct` 是 **dialect 专属**选项，在 SQLite 上被忽略
（而单测跑的就是 `sqlite+aiosqlite:///:memory:`）。所以本文件只能验
「ORM 确实声明了它」—— 真正的行为验证在两个**真库**上做，见
`alembic/versions/p8_009_nulls_distinct_unique.py` 与 TODOS 里的复核清单。

⚠️ 也因此：**别把这个守卫的测试删掉**。它是「迁移与 ORM 是否同步」的唯一
自动检查 —— `alembic check` 比的是类型与约束定义，不比 `nulls_not_distinct`
在 SQLite 侧的效果。
"""
from __future__ import annotations

import pytest

from app.models.report import ReportDefinition, ReportStyleRow

#: `(表, 约束名, 列)`
SCOPED_UNIQUES = [
    (ReportDefinition, "uq_report_definitions_project_name", ("project_id", "name")),
    (ReportStyleRow, "uq_report_styles_scope_version",
     ("report_type", "project_id", "version")),
]


@pytest.mark.parametrize("model,con_name,cols", SCOPED_UNIQUES)
def test_scoped_unique_declares_nulls_not_distinct(model, con_name, cols):
    """含可空 `project_id` 的唯一约束必须声明 `NULLS NOT DISTINCT`。"""
    con = next(c for c in model.__table__.constraints if c.name == con_name)
    assert tuple(con.columns.keys()) == cols, \
        f"{con_name} 的列变了：{tuple(con.columns.keys())}"
    # SQLAlchemy 把 dialect 专属开关放在 dialect_options 里
    assert con.dialect_options["postgresql"]["nulls_not_distinct"] is True, (
        f"{con_name} 没有声明 postgresql_nulls_not_distinct —— "
        "PG 上 NULL 互不相等，公司级行（project_id IS NULL）完全绕开这个约束。")


def test_null_distinct_would_actually_let_duplicates_through():
    """把这条写清楚：为什么「看起来有唯一约束」其实等于没有。

    不是测试 PG 的行为（那要用真库），而是把这个约束的**语义前提**
    摆在测试里 —— 免得将来有人把 `NULLS NOT DISTINCT` 去掉时，
    只看到「约束还在」就以为安全网没变。
    """
    # PG 语义：UNIQUE 里任一列为 NULL 时，该行**不参与**唯一性判定。
    # 于��� (NULL, '泵数据表') 出现两次是合法的。
    assert (None, "泵数据表") == (None, "泵数据表")   # 语义上「相等」
    assert len({(None, "泵数据表"), (None, "泵数据表")}) == 1  # 集合去重后只剩一个
    # 结论：靠「查一下有没有」的应用层检查防不住并发两次插入 ——
    # 两个请求都查到「没有」，各自插入，于是两个公司级同名定义并存。
    # 与 test_rbac / numbering 那几个「asyncio.Lock 串行化」的测试同族：
    # 那里靠锁补 SQLite 的缺口，这里必须靠数据库本身。
