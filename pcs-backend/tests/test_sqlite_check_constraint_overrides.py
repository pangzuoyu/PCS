"""conftest 里 SQLite CHECK 替身与 PostgreSQL 原式的**语义等价性**。

## 为什么要单独测这个

`tests/conftest.py` 的 `_SQLITE_CHECK_OVERRIDES` 是**人手写的替身**：ORM 里的
`future_dated_forbidden_chk` 表达式是 PG 专有的 `interval '1 second'` 类型
字面量，SQLite 的分词器在 CREATE TABLE 阶段就报 syntax error，只能按约束名
整条替换成 `julianday` 等价式。

替身带来一个原方案没有的风险：**两边可能悄悄不等价，而测试永远绿** ——
测试跑的是 SQLite 替身，真库跑的是 PG 原式，谁也没测过对方。

所以这里把两边都**渲染出来、真的建表、真的插数据**，用同一张判定表逐条比对。
改动任一侧的表达式，这个测试就红。

## 判定表的构造

`_CASES` 同时喂给两个引擎。日期用**不带时区**的 naive 字符串：PG 侧列是
`TIMESTAMP WITHOUT TIME ZONE`，SQLite 侧存 TEXT，两边都对齐到同一种朴素时间。
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

from app.core.config import get_settings
from app.db.base import Base
from app.models.psv_standards import ProjectCalculationStandardProfile

_CONSTRAINT = "future_dated_forbidden_chk"
_TABLE = "project_calculation_standard_profiles"

# (标签, effective_from, created_at, 期望是否放行)
# 「期望」依据约束名本身的意思：effective_from 不得比 created_at 晚出 1 秒以上
# （1 秒容差是给应用侧时间戳与 DB 侧 now() 的时钟差留的）。
_CASES = [
    ("完全同时刻", "2020-01-01 00:00:00", "2020-01-01 00:00:00", True),
    ("过去 1 秒", "2019-12-31 23:59:59", "2020-01-01 00:00:00", True),
    ("容差内的亚秒", "2020-01-01 00:00:00.500000", "2020-01-01 00:00:00", True),
    ("容差边界 1 秒整", "2020-01-01 00:00:01", "2020-01-01 00:00:00", True),
    ("超出容差 2 秒", "2020-01-01 00:00:02", "2020-01-01 00:00:00", False),
    ("远未来", "2020-06-01 00:00:00", "2020-01-01 00:00:00", False),
]

_PROFILES = {
    "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "project_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "discipline": "PSV",
    "profile_code": "API",
    "standard_refs_json": "[]",
    # 其余列交给 server_default / ORM 默认值
}


def _table() -> sa.Table:
    return Base.metadata.tables[_TABLE]


def _render_postgres() -> str:
    from sqlalchemy.schema import CreateTable

    return str(CreateTable(_table()).compile(dialect=postgresql.dialect()))


def _render_sqlite() -> str:
    from sqlalchemy.schema import CreateTable

    return str(CreateTable(_table()).compile(dialect=sqlite.dialect()))


def test_postgres_renders_the_interval_literal():
    """真库那一侧必须还是 PG 的 interval 字面量 —— 替身不能反过来污染它。"""
    ddl = _render_postgres().lower()
    assert f"constraint {_CONSTRAINT.lower()} check" in ddl
    assert "interval '1 second'" in ddl


def test_sqlite_renders_the_julianday_substitute():
    """测试库那一侧走 conftest 替身。"""
    ddl = _render_sqlite().lower()
    assert f"constraint {_CONSTRAINT.lower()} check" in ddl
    assert "julianday(effective_from)" in ddl
    assert "interval" not in ddl, "PG 的 interval 字面量漏进了 SQLite DDL"


@pytest.mark.parametrize(("label", "eff", "cre", "accepted"), _CASES,
                         ids=[c[0] for c in _CASES])
def test_sqlite_substitute_matches_expected(label, eff, cre, accepted):
    """替身在 SQLite 上按判定表工作。"""
    engine = sa.create_engine("sqlite:///:memory:")
    _table().create(engine)
    row = dict(_PROFILES)
    row["effective_from"] = dt.datetime.fromisoformat(eff)
    row["created_at"] = dt.datetime.fromisoformat(cre)
    with engine.begin() as conn:
        try:
            conn.execute(_table().insert(), row)
            got = True
        except sa.exc.IntegrityError:
            got = False
    assert got is accepted, f"{label}: 期望{'放行' if accepted else '拒绝'}"


@pytest.mark.parametrize(("label", "eff", "cre", "accepted"), _CASES,
                         ids=[c[0] for c in _CASES])
def test_postgres_original_matches_same_verdicts(label, eff, cre, accepted):
    """**PG 原式在同一张判定表上给出完全相同的裁决。**

    这是本文件的核心断言：两套表达式不是「各测各的」，而是**同一张表的两个
    实现**。任何一侧被改动而另一侧没跟上，这里立刻红。

    需要 `pcs_test` 可连（不在 CI 的默认配置里），连不上就跳过 —— 缺了真库
    这一侧不能算通过，但也别把整份测试拖红。
    """
    if not _postgres_available():
        pytest.skip("pcs_test 不可连")
    assert _verdict_on_postgres(eff, cre) is accepted, label


def _postgres_available() -> bool:
    try:
        eng = _probe_engine()
        with eng.connect():
            pass
        eng.dispose()
        return True
    except sa.exc.SQLAlchemyError:
        return False


def _probe_engine() -> sa.Engine:
    """指向 `pcs_test` 的同步引擎。

    库名/凭据一律从 `get_settings().database_url` 派生（与 `tests/test_schema.py`
    同一套做法），**不把连接串写进源码** —— 写死的口令会跟着 git 走。

    换到 `pcs_test` 而不是开发库：这里要真的 CREATE / DROP 一张探针表。
    """
    url = sa.engine.make_url(get_settings().database_url)
    return sa.create_engine(url.set(database="pcs_test"))


def _verdict_on_postgres(effective_from: str, created_at: str) -> bool:
    """在真库上真建一张只含该 CHECK 的表，跑一次 INSERT 看是否放行。"""
    meta = sa.MetaData()
    # 只取该 CHECK 的表达式文本，另起一张两列表 —— 不依赖整张表的其余 NOT NULL 列
    expr = next(c.sqltext for c in ProjectCalculationStandardProfile.__table__.constraints
                if getattr(c, "name", None) == _CONSTRAINT)
    probe = sa.Table(
        "_probe_future_dated", meta,
        sa.Column("effective_from", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(expr, name=_CONSTRAINT),
    )
    engine = _probe_engine()
    try:
        with engine.begin() as conn:
            probe.drop(conn, checkfirst=True)
            probe.create(conn)
            try:
                conn.execute(probe.insert(), {
                    "effective_from": dt.datetime.fromisoformat(effective_from),
                    "created_at": dt.datetime.fromisoformat(created_at),
                })
                return True
            except sa.exc.IntegrityError:
                return False
    finally:
        with engine.begin() as conn:
            probe.drop(conn, checkfirst=True)
        engine.dispose()


def test_no_unmapped_check_constraints():
    """conftest 替身表里每一条都必须在 ORM 里真有同名约束。

    反过来才是危险方向：ORM 加了新 CHECK 但忘了写替身，SQLite 建表会当场
    syntax error（这条会自然暴露）。这条测的是别有人往替身表里塞一条 ORM
    并不存在的约束 —— 那样 SQLite 与真库会无声地越走越远。
    """
    from tests.conftest import _SQLITE_CHECK_OVERRIDES

    orm = {
        c.name
        for t in Base.metadata.tables.values()
        for c in t.constraints
        if getattr(c, "name", None)
    }
    assert set(_SQLITE_CHECK_OVERRIDES) <= orm, (
        "conftest 里有 ORM 并不存在的 CHECK 替身："
        f"{set(_SQLITE_CHECK_OVERRIDES) - orm}"
    )
