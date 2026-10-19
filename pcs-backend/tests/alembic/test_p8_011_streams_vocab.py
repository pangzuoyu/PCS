"""`streams` 词表 CHECK 的迁移（p8_011）的结构自检。

## 为什么单测抓不到

`tests/conftest.py` 从 `SA_Base.metadata.create_all` 建**内存 SQLite** 表，
**不跑迁移**。所以「迁移写没写、写对不对、CHECK 的值对不对」，4500+ 单测
一律绿 —— 这是本仓反复踩的**漂移盲区**（CLAUDE.md 有专节）。

迁移真正的验证只有两条路：
1. 在**真库**上 `alembic upgrade` + `alembic check`（退出码 **255**）；
2. **对迁移文件本身做静态断言**（本文件）。

本文件做第 2 条 —— 它不需要真库，因此可以进单测，也是 CI/本地都能跑的。

## 为什么迁移里也不能硬编码取值

迁移里写死 `('VAPOR','LIQUID',...)` 会与 `app/models/enums.py` 形成
**第二份定义** —— 那正是 bug-187~191 这一族的根（同一概念两份定义，
漂移只是时间问题）。所以：

- `upgrade()` **从枚举取值**（`_enum_values()`）；
- 本测试锁住「ORM 声明的 CHECK 表达式里确实包含全部枚举值」——
  即便有人后来把取值改硬编码了，这里也会红。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.models.enums import StreamDataMode, StreamPhase, StreamSourceType
from app.models.project import Stream

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "p8_011_streams_vocab_constraints.py"
)


def _orm_check_sql(name: str) -> str:
    for c in Stream.__table__.constraints:
        if c.name == name:
            return str(c.sqltext)
    raise AssertionError(f"ORM 没有声明 {name}")


class TestMigrationFileShape:
    def test_迁移文件存在(self):
        assert _MIGRATION.is_file()

    def test_三条CHECK都在ORM里声明(self):
        """迁移建了、ORM 没声明 ⇒ `alembic check` 会报 add_constraint。"""
        names = {c.name for c in Stream.__table__.constraints}
        for col in ("phase", "data_mode", "source_type"):
            assert f"ck_streams_{col}" in names

    def test_迁移里的取值来自枚举而非硬编码(self):
        """AST 层面确认 `upgrade()` 没有把 IN 列表写成字面量。

        这是「防止第二份定义」的唯一机械保证 —— 只看运行时行为抓不到它
        （硬编码的值**恰好相等**时行为完全一样）。
        """
        tree = ast.parse(_MIGRATION.read_text())
        upgrade_fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "upgrade"
        )
        # ⚠️ 必须同时查 list / tuple / set / frozenset 调用 —— 第一版只查
        # `ast.List`，而我实际写硬编码时用的是 **tuple**，于是这条守卫
        # 对真实的违规**完全无效**（变异验证抓出来的）。
        # ⇒ 守卫要比它守的东西宽，不是窄。
        _SEQ = (ast.List, ast.Tuple, ast.Set)
        literals = [
            n for n in ast.walk(upgrade_fn)
            if isinstance(n, _SEQ) and len(n.elts) >= 3
            and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts)
        ]
        assert not literals, (
            "upgrade() 里出现了 ≥3 个字符串组成的序列字面量 —— 取值必须来自 "
            "_enum_values()，否则就与 app/models/enums.py 形成了第二份定义"
        )


class TestOrmChecksMatchEnums:
    """ORM 的 CHECK 表达式必须**逐个包含**枚举的全部取值。"""

    @pytest.mark.parametrize(
        "col,enum_",
        [
            ("phase", StreamPhase),
            ("data_mode", StreamDataMode),
            ("source_type", StreamSourceType),
        ],
    )
    def test_CHECK表达式含全部枚举值(self, col, enum_):
        sql = _orm_check_sql(f"ck_streams_{col}")
        missing = [v.value for v in enum_ if f"'{v.value}'" not in sql]
        assert not missing, (
            f"ck_streams_{col} 少了这些值: {missing} —— "
            "枚举加了值但 CHECK 没跟 ⇒ 合法值写不进去"
        )

    @pytest.mark.parametrize(
        "col,enum_",
        [("phase", StreamPhase), ("data_mode", StreamDataMode),
         ("source_type", StreamSourceType)],
    )
    def test_CHECK允许NULL(self, col, enum_):
        """三列都可空（`phase` 尤其：认不出词表外值时就是 NULL）。"""
        assert f"{col} IS NULL" in _orm_check_sql(f"ck_streams_{col}")


class TestRawPhaseHasNoCheck:
    def test_raw_phase故意没有CHECK(self):
        """它的用途就是装下词表外的值 —— 加 CHECK 就把用途删了。"""
        names = {c.name for c in Stream.__table__.constraints}
        assert not any(n and "raw_phase" in n for n in names)

    def test_raw_phase是ORM列(self):
        assert "raw_phase" in Stream.__table__.columns
        col = Stream.__table__.columns["raw_phase"]
        assert col.nullable is True


class TestEnumVocabularyCounts:
    """把取值**数量**钉住 —— 数量变了就该有人看一眼。

    不是为了防漂移（那由上面几条负责），而是因为 2026-10-19 的实测结论：
    `source_type` 的 description 写 5 个、实际 13 个；`sign_status` 写 4 态、
    实际 9 态。**数量对不上是这一族 bug 最先露出来的信号。**
    """

    def test_三个词表的基数(self):
        assert len(list(StreamPhase)) == 4
        assert len(list(StreamDataMode)) == 3
        assert len(list(StreamSourceType)) == 13

    def test_source_type含全部CALCULATED出口流(self):
        calc = [t.value for t in StreamSourceType if t.value.endswith("_CALCULATED")]
        assert len(calc) == 10, (
            f"`*_CALCULATED` 现在是 {len(calc)} 个：{calc} —— "
            "DEVICE_CALCULATED 曾因散落字面量被遗漏过一次（A-03/C-05）"
        )
