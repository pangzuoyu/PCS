"""REPORT_BUILDER 执行引擎（P8b b7）。

把一份 `ReportDefinition` 变成一张表：**声明来自定义，执行走 `query_engine`**
（15 个操作符与 JOIN 白名单只有一份实现）。

## 三条不能省的边界

1. **MaxRows 是硬闸，截断必须明说。** 静默截断 = 用户拿到少了几千行的
   报表却毫无察觉。结果里带 `truncated`，导出件上也要看得见（b8）。
2. **临时过滤条件绝不回写定义。** 执行面板允许用户临时筛一下再导出，
   那是一次性的操作；写回 `definition_json.FilterConditions` 会让下一个
   打开这份定义的人继承别人的一次临时筛选。快照进审计，不进定义。
3. **审计必写，且带条件快照。** `report_execution_logs` 是执行的账本；
   只存 `def_id` 的话，定义改过之后就再也复现不出当时查了什么。

## 多源：每源一次 SELECT + Python 组装（用户 2026-10-09 裁决）

主源先查（带过滤 + 排序 + MaxRows），从源按白名单关联键
`WHERE key IN (...)` **一次批量查**，再在 `query_engine.assemble` 里
dict lookup 关联。**不生成 SQL JOIN** —— 白名单是声明，不是让用户拼
任意笛卡尔积的口子。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import ReportDefinition, ReportExecutionLog
from app.services.exceptions import PcsError
from app.services.report import query_engine as qe
from app.services.report.datasource_registry import DATASOURCES, join_key_for

#: 从源批量查询的分批大小。IN 列表过长会让语句膨胀到不可用。
_BATCH_SIZE = 5000


@dataclass(frozen=True)
class ExecutionResult:
    """一次执行的产出（渲染前）。

    `headers` / `rows` 是给渲染器的中间表示；`truncated` 单独带出来是
    因为「截断了」必须在成品上可见，不能只存在于返回值里。
    """

    headers: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    def_version: str
    snapshot: dict[str, Any] = field(default_factory=dict)


def _visible_fields(defn: dict[str, Any]) -> list[tuple[str, str, str]]:
    """取出要渲染的字段，**跳过 `visible=False`**，按 `order` 排。

    返回 `(source, field, 表头)`。表头取别名，别名为空则退回注册表 label
    —— 用户在字段树里看到的 label 就是默认表头，别名是覆盖它。

    ⚠️ 排序键用 `order` 而不是列表下标：SPEC §3.2.2(3) 有「拖拽排序」，
    拖拽产生的 `order` 未必等于当前数组位置（前端可能只重排 order）。
    按下标排会让「拖了没反应」。
    """
    out: list[tuple[int, str, str, str]] = []
    for i, sel in enumerate(defn.get("SelectedFields") or []):
        if not sel.get("visible", True):
            continue
        src, fname = sel["source"], sel["field"]
        alias = (sel.get("alias") or "").strip()
        label = alias or DATASOURCES[src].fields[fname].label
        out.append((sel.get("order", i), src, fname, label))
    out.sort(key=lambda t: (t[0], t[1], t[2]))
    return [(src, fname, label) for _o, src, fname, label in out]


async def _fetch_source(db: AsyncSession, source: str, fields: list[str],
                        filter_spec: dict | None, sort_fields: list[str],
                        limit: int) -> list[dict]:
    """单源取数，产出 list[dict]（键是字段名）。

    顺序：先 `build_select` 再 `where` —— `apply_filters` 返回的是
    ColumnElement（布尔表达式）而不是 Select，顺序反了会得到
    `'Comparator' object has no attribute 'order_by'`。
    """
    stmt = qe.build_select(source, fields)
    stmt = stmt.where(qe.apply_filters(filter_spec))
    if sort_fields:
        stmt = qe.apply_sort(stmt, sort_fields)
    stmt = qe.paginate(stmt, limit=limit)
    result = await db.execute(stmt)
    columns = list(result.keys())
    return [dict(zip(columns, row, strict=True)) for row in result.all()]


async def _fetch_join_rows(db: AsyncSession, *, source: str, join_field: str,
                           keys: list) -> list[dict]:
    """从源批量查（`WHERE key IN (...)`），不是 N 次查询。"""
    if not keys:
        return []
    cols = list(DATASOURCES[source].fields)
    stmt = qe.build_select(source, cols)
    out: list[dict] = []
    for i in range(0, len(keys), _BATCH_SIZE):
        chunk = keys[i:i + _BATCH_SIZE]
        result = await db.execute(stmt.where(_attr(source, join_field).in_(chunk)))
        names = list(result.keys())
        out.extend(dict(zip(names, r, strict=True)) for r in result.all())
    return out


def _attr(source: str, field_name: str):
    """数据源表上的一列（JOIN 关联键必须是最外层的真实列）。"""
    ds = DATASOURCES[source]
    model = qe._model_for(ds)          # noqa: SLF001 —— 同模块，刻意复用解析逻辑
    return getattr(model, field_name)


async def execute_definition(
    db: AsyncSession, *, def_id: uuid.UUID, user_id: uuid.UUID | None,
    project_id: uuid.UUID | None = None,
    temporary_filters: dict[str, Any] | None = None,
    temporary_max_rows: int | None = None,
    output_format: str | None = None,
) -> ExecutionResult:
    """执行一份定义并写执行日志。**纯查询 + 审计，不写 report_files**。

    文件渲染与 `report_files` 由调用方（ARQ 任务体）接上 —— 这里是
    「取到什么」与「渲染成什么」的分界。

    ## 项目作用域是硬边界，不是过滤条件

    `report_definitions.project_id` 可空（NULL = 公司级模板）。若就此放行，
    执行会**不带任何项目过滤**地全表扫描 —— 用户把一份公司级模板拖进执行
    面板，得到的是全库所有项目的数据。解析不到项目时直接 400，
    不「那就不筛吧」。
    """
    row = await db.get(ReportDefinition, def_id)
    if row is None:
        raise PcsError(f"报表定义不存在：{def_id}",
                       code="REPORT_DEFINITION_NOT_FOUND", status=404)
    if row.status != "PUBLISHED":
        raise PcsError(
            f"只有已发布的定义可执行，该定义当前是 {row.status}。",
            code="REPORT_DEFINITION_STATE", status=409,
        )
    scope = project_id or row.project_id
    if scope is None:
        raise PcsError(
            "该报表定义未绑定项目（公司级模板），执行时必须指定 project_id。"
            "**不能默认全库查询** —— 那会把别的项目的数据一起导出去。",
            code="REPORT_PROJECT_SCOPE_REQUIRED", status=400,
        )

    defn = dict(row.definition_json or {})
    selected = _visible_fields(defn)
    if not selected:
        raise PcsError("定义里没有可显示的字段（SelectedFields 全是 visible=false）",
                       code="REPORT_DEFINITION_INVALID", status=400)

    sources = [s.get("source") for s in defn.get("DataSources") or []]
    primary = sources[0]
    limit = temporary_max_rows or row.max_rows or 10000

    fields_by_source: dict[str, list[str]] = {}
    for src, fname, _label in selected:
        fields_by_source.setdefault(src, []).append(fname)

    # 项目过滤与用户条件**合并**成一个 AND 组。
    # ⚠️ 项目过滤不是「用户条件的一部分」：它是越权边界。把它拼进用户
    # 可编辑的条件列表里，意味着将来有人改条件构造时有机会把它挤掉，
    # 而挤掉之后报表仍然跑得通、仍然返回 200 —— 只是多了别人的数据。
    # 故这里**独立地**与用户条件合并，两者都是必需项，谁也替代不了谁。
    base_conds = defn.get("FilterConditions") or []
    conditions: list[dict[str, Any]] = [
        # ⚠️ value 必须是**原生 UUID**，不能是字符串。本仓的 `Uuid` 列
        # bind processor 直接调 `.hex`，传 str 会炸
        # `AttributeError: 'str' object has no attribute 'hex'` ——
        # 而 `apply_filters` 不校验类型，所以这个错一路冒到 SQL 才炸。
        {"operator": "EQ", "source": primary,
         "field": _project_field(primary), "value": scope},
    ]
    conditions += ([temporary_filters] if temporary_filters else base_conds)
    group = {"operator": "AND", "conditions": conditions}

    sort_fields = [f["field"] for f in (defn.get("SortBy") or [])]
    sort_fields = [f for f in sort_fields if f in fields_by_source.get(primary, [])]

    main_rows = await _fetch_source(
        db, primary, fields_by_source[primary], group, sort_fields, limit + 1)
    truncated = len(main_rows) > limit
    main_rows = main_rows[:limit]

    rows_by_source: dict[str, list[dict]] = {primary: main_rows}
    join_keys: list[tuple[str, str, str, str]] = []
    for extra in sources[1:]:
        a_key, b_key = join_key_for(primary, extra)     # 白名单外 → 400
        join_keys.append((primary, a_key, extra, b_key))
        rows_by_source[extra] = await _fetch_join_rows(
            db, source=extra, join_field=b_key,
            keys=[r.get(a_key) for r in main_rows if r.get(a_key) is not None])

    merged = qe.assemble(rows_by_source, join_keys, primary, fields_by_source)
    headers = [label for _s, _f, label in selected]
    table = [[r.get(fname if src == primary else f"{src}.{fname}")
              for src, fname, _l in selected] for r in merged]

    snapshot = {
        **defn,
        "def_id": str(def_id),
        "FilterConditions": [temporary_filters] if temporary_filters else base_conds,
        "project_id": str(scope),
        "max_rows": limit,
        "output_format": output_format or row.output_format,
    }
    db.add(ReportExecutionLog(
        def_id=row.def_id, def_version=row.version,
        condition_snapshot=snapshot, row_count=len(table),
        output_format=output_format or row.output_format,
        executed_by=user_id,
        is_temporary_adjust=temporary_filters is not None,
    ))
    await db.flush()

    return ExecutionResult(
        headers=headers, rows=table, row_count=len(table),
        truncated=truncated, def_version=row.version, snapshot=snapshot,
    )


def _project_field(source: str) -> str:
    """数据源的项目列名。

    各源统一叫 `project_id`（`RecordMixin` 的 declared_attr），但仍从注册表
    取而不是硬编码：注册表是「哪些字段可查询」的真相来源，硬编码会在有人
    重命名某张表的列时静默失效 —— 而失效的表现是**少一个过滤条件**，
    不是报错。
    """
    ds = DATASOURCES[source]
    if "project_id" not in ds.fields:
        raise PcsError(
            f"数据源 {source} 没有 project_id 列，无法按项目隔离执行。",
            code="REPORT_PROJECT_SCOPE_REQUIRED", status=400,
        )
    return "project_id"


__all__ = ["ExecutionResult", "execute_definition"]