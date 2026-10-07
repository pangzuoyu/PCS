"""描述文本覆盖率闸 —— 本体论 §3.4 约束② 的可落地形态.

契约全文见 `docs/PCS-NOTE-3.4-描述文本契约-2026-10-07.md`。

## 它做什么

对 `*_result` / `*_results` 表的每个 JSONB 列，检查是否登记了对应的**载荷
Pydantic 模型**；登记了就比对模型顶层 `description` 与该列的 **ORM Column
comment** 是否逐字相等。

**不经 PG。** `COMMENT ON` 是 alembic 管辖的 schema 元数据，与描述文本无关
（2026-10-07 用户裁决：注释不进契约）。本闸两端都是 Python 源码。

## 为什么是「只拦倒退」而不是「漂移即 fail」

SPEC §3.4 约束② 写的是「漂移即 fail」。该句的前提是**约束①已落地** ——
即每个 `*_result` 表的 JSONB 载荷都有对应的嵌套 Pydantic 模型。

实测该前提不成立：**29 张表里 21 张（72%）一个都没有**，另外 8 张有的也只是
API 信封（CreateRequest / Response / ListResponse），不是载荷模型。
SPEC 自己举的例子 `HeatDesignParametersSchema` 全仓 0 命中 —— 它描述的是一个
从未存在过的模型。

此刻写一个「全量比对」的闸，只会从第一天起就报几十条没人能修的红，然后被整体关掉 ——
这就是 cerebrum 里记的「守门恒报噪声 = 狼来了」。反方向（恒报绿）同样危险。

所以这里取第三条路：**把欠账量化成一个可下降的数字，只保证它不涨。**
- 覆盖率 >= 基线 → 0
- 覆盖率 < 基线，或已登记项被改坏 → 1

约束①补齐后本闸自然升级为对已登记项的强阻断，无需改结构。

## 登记表而非命名推断

`_REGISTRY` 显式写死「哪张表的哪个列对应哪个模型」。**不做任何命名推断** ——
本项目 JSONB 列命名高度不规则：`pump_results` 有 15 个（`basic_info_json` /
`fluid_properties_json` / `suction_calculation_json` …），`heat_results` 有
`shell_params` / `tube_params` / `ache_params` 这些**不带 `_json` 后缀**的。
任何 `{表名驼峰}{列名驼峰}` 的猜测都会在这里炸出大量假阳性。

未登记 = 欠账，一眼可见；补模型时只需加一行。
"""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field

import app.models  # noqa: F401  触发全部表注册
from app.db.base import Base

# (表名, 列名或 None=整表, "模块:类名")
#
# 当前为空 —— 29 张表全部欠账。补一个模型就加一行，覆盖率 +1。
# 列名 None 表示该表的载荷对应一个整表级模型（而非某个具体列）。
REGISTRY: dict[str, tuple[str | None, str]] = {}


@dataclass
class Result:
    """一次检查的结论."""

    total_tables: int
    covered: int
    violations: list[str] = field(default_factory=list)
    debt_tables: list[str] = field(default_factory=list)
    registered: int = 0
    json_columns: int = 0
    columns_with_comment: int = 0

    @property
    def baseline_ok(self) -> bool:
        return len(self.violations) == 0


def _result_tables() -> dict[str, list[str]]:
    """表名 -> 该表的 JSONB 列名列表（只取 *_result / *_results）."""
    out: dict[str, list[str]] = {}
    for name, table in sorted(Base.metadata.tables.items()):
        if not name.endswith(("_result", "_results")):
            continue
        cols = [
            c.name
            for c in table.columns
            if type(c.type).__name__ in ("JSONB", "JSON")
        ]
        if cols:
            out[name] = cols
    return out


def _resolve(target: str):
    """'模块:类名' -> 类对象；解析不到返回 None."""
    module_name, _, cls_name = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None
    return getattr(module, cls_name, None)


def describe(target: str) -> str | None:
    """取登记模型的顶层描述（Field(description=...) 优先，否则用 docstring）."""
    cls = _resolve(target)
    if cls is None:
        return None
    field_info = getattr(cls, "model_config", None) or {}
    field_info = field_info.get("json_schema_extra") or {}
    if isinstance(field_info, dict) and field_info.get("description"):
        return str(field_info["description"])
    doc = (cls.__doc__ or "").strip()
    return doc.splitlines()[0].strip() if doc else None


def orm_comment(table: str, column: str | None) -> str | None:
    """取 ORM Column 的 comment."""
    tbl = Base.metadata.tables.get(table)
    if tbl is None:
        return None
    if column is None:
        return tbl.comment
    col = tbl.columns.get(column)
    return col.comment if col is not None else None


def check_entry(
    *, table: str, column: str | None, target: str, expect_description: str | None = None
) -> list[str]:
    """检查单个登记项。expect_description 省略时以 ORM comment 为准."""
    violations: list[str] = []
    actual = describe(target)
    if actual is None:
        return [f"{table}.{column or '(整表)'}: 载荷模型 {target} 不存在"]

    expected = expect_description
    if expected is None:
        expected = orm_comment(table, column)
    if expected is None:
        violations.append(
            f"{table}.{column or '(整表)'}: ORM comment 为空，无法与载荷模型比对"
        )
        return violations

    if actual.strip() != expected.strip():
        violations.append(
            f"{table}.{column or '(整表)'}: 描述不一致\n"
            f"      ORM comment : {expected!r}\n"
            f"      模型 description: {actual!r}"
        )
    return violations


def check() -> Result:
    """跑一次全量检查."""
    tables = _result_tables()
    violations: list[str] = []
    debt: list[str] = []
    registered = 0
    covered = 0
    json_columns = sum(len(cols) for cols in tables.values())
    columns_with_comment = sum(
        1
        for name in tables
        for col in tables[name]
        if orm_comment(name, col)
    )

    for table in sorted(tables):
        entry = REGISTRY.get(table)
        if entry is None:
            debt.append(table)
            continue
        column, target = entry
        registered += 1
        problems = check_entry(table=table, column=column, target=target)
        if problems:
            violations.extend(problems)
        else:
            covered += 1

    return Result(
        total_tables=len(tables),
        covered=covered,
        violations=violations,
        debt_tables=debt,
        registered=registered,
        json_columns=json_columns,
        columns_with_comment=columns_with_comment,
    )


def main() -> int:
    result = check()
    pct = (
        0.0
        if result.total_tables == 0
        else round(100.0 * result.covered / result.total_tables, 1)
    )
    print(
        f"描述文本覆盖: {result.covered}/{result.total_tables} 表 ({pct}%)"
        f"，已登记 {result.registered} 项，欠账 {len(result.debt_tables)} 张表"
    )
    # 约束② 的另一端：ORM comment 自身有没有。这是 §3.4 约束③「评审现有 JSONB
    # 字段的 Pydantic Schema 覆盖情况」的一半 —— 另外一半（载荷模型）在上面的欠账里。
    comment_pct = (
        0.0
        if result.json_columns == 0
        else round(100.0 * result.columns_with_comment / result.json_columns, 1)
    )
    print(
        f"ORM comment 覆盖: {result.columns_with_comment}/{result.json_columns} "
        f"个 JSONB 列 ({comment_pct}%) —— 约束② 的另一端"
    )

    if result.violations:
        print(f"\nFAIL: {len(result.violations)} 处已登记项被改坏:")
        for v in result.violations:
            print(f"  {v}")

    if result.debt_tables:
        print("\n欠账（未登记载荷模型，不阻断；本体论 §3.4 约束①）:")
        for t in result.debt_tables:
            print(f"  - {t}")

    if result.violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())