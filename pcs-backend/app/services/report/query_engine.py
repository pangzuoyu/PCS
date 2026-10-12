"""取数引擎 —— 过滤/排序/字段选择/NULL 处理的**唯一实现**。

consumer：collector（P8a 固定查询）/ builder_service（P8b 动态查询）。
两者都只写「查什么」，「怎么查」全在这里 —— 15 个操作符与 JOIN 白名单
各只有一份实现（用户 2026-10-08 裁决；两处各写一遍必然语义漂移）。

## 安全契约（三条，任一破掉就是漏洞）

1. **一切走 bind params**。没有任何 f-string / `%` / `+` 拼进 SQL 文本。
   测试 `test_operator_translates_to_parameterized_sql` 逐个操作符断言
   值不出现在编译后的 SQL 里。
2. **字段名必须存在于 datasource_registry**。这既是防注入，也是防幻觉列 ——
   字段树里存了个不存在的列名时，这里拦住，不让用户拿到 500。
   ⚠️ `getattr(Model, field)` 是安全的（属性查找，不 eval），但拿到的
   若不是 `InstrumentedAttribute` 就说明字段不在表上，必须拒。
3. **缺 value 绝不静默放行**。`{"operator": "IS_NULL"}` 之外的算子缺 value
   时抛 `REPORT_FILTER_VALUE_MISSING`；**返回「恒真」表达式 = 返回全表**，
   那比报错危险得多 —— 用户以为筛了，其实拿到的是全量数据。

## 多源策略（用户 2026-10-09 裁决）

**每源一次 SELECT + Python 组装，不生成 SQL JOIN。** JOIN 白名单只用于
校验（拒绝不在白名单的关联键），不用于构造 JOIN 子句。理由：白名单 5 对
全是「主表 + 从表」，从表行数远小于主表；10s 性能预算下 10000 行 × 2 源的
Python 组装约 1–2s，不是瓶颈；而 SQL JOIN 会引入第二套执行路径。

组装的四条实现约束见 `assemble()`。
"""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.db.base import Base
from app.services.exceptions import PcsError
from app.services.report.datasource_registry import DATASOURCES, join_key_for

logger = logging.getLogger(__name__)
_MODEL_CACHE: dict[str, type] = {}

# SPEC §3.2.2(4)：15 个操作符，少一个就是功能缺口。
SUPPORTED_OPS = frozenset({
    "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "IN", "NOT_IN", "CONTAINS",
    "STARTS_WITH", "ENDS_WITH", "IS_NULL", "IS_NOT_NULL", "BETWEEN", "LIKE",
})
_VALUELESS = frozenset({"IS_NULL", "IS_NOT_NULL"})
_LIST_OPS = frozenset({"IN", "NOT_IN"})


def _datasource(key: str):
    ds = DATASOURCES.get(key)
    if ds is None:
        raise PcsError(f"未知数据源：{key}", code="REPORT_DATASOURCE_UNKNOWN",
                       status=400)
    return ds


def _model_for(ds) -> type:
    """表名 → ORM 类。

    ⚠️ 不能用 `Base.registry._class_registry[表名]` —— 那个字典按**类名**索引
    （`EquipmentList`），注册表里存的是表名（`equipment_list`）。
    这里扫 mapper 的 local_table 反查，一次缓存。
    """
    cached = _MODEL_CACHE.get(ds.model)
    if cached is not None:
        return cached
    for mapper in Base.registry.mappers:
        if mapper.local_table is not None and mapper.local_table.name == ds.model:
            _MODEL_CACHE[ds.model] = mapper.class_
            return mapper.class_
    raise PcsError(f"数据源 {ds.key} 的表 {ds.model} 没有对应的 ORM 类",
                   code="REPORT_DATASOURCE_UNKNOWN", status=400)


def _column(source: str, field: str) -> InstrumentedAttribute:
    """把注册表里的字段名解析成 ORM 列属性。

    `getattr(Model, field)` 是属性查找不是 eval，本身不构成注入；但解析结果
    **必须**是 `InstrumentedAttribute` —— 否则说明这个字段名在表上不存在
    （或是个方法/关系），必须拒。
    """
    ds = _datasource(source)
    spec = ds.fields.get(field)
    if spec is None:
        raise PcsError(
            f"字段 {source}.{field} 不在数据源注册表中。"
            f"可用字段：{', '.join(sorted(ds.fields))}",
            code="REPORT_FIELD_UNKNOWN", status=400,
        )
    model = _model_for(ds)
    if spec.is_jsonb_key:
        # JSONB 子键不是列 —— 取容器列，过滤时用 ->> 下钻（见 _build_condition）
        container = spec.name.split(".", 1)[0]
        return getattr(model, container)
    attr = getattr(model, field, None)
    if not isinstance(attr, InstrumentedAttribute):
        raise PcsError(f"字段 {source}.{field} 不在 ORM 表 {ds.model} 上",
                       code="REPORT_FIELD_UNKNOWN", status=400)
    return attr


def _jsonb_col(source: str, field: str):
    """返回 (容器列, 子键) —— JSONB 字段才需要。"""
    ds = _datasource(source)
    spec = ds.fields[field]
    container, _, key = spec.name.partition(".")
    model = _model_for(ds)
    return getattr(model, container), key


def _need_value(op: str, value: Any) -> Any:
    if op in _VALUELESS:
        return None
    if value is None or value == "":
        raise PcsError(
            f"操作符 {op} 需要 value。"
            f"**不能静默忽略** —— 返回恒真表达式等于返回全表。",
            code="REPORT_FILTER_VALUE_MISSING", status=400,
        )
    if op in _LIST_OPS and not isinstance(value, (list, tuple, set)):
        raise PcsError(f"操作符 {op} 需要列表 value，实得 {type(value).__name__}",
                       code="REPORT_FILTER_VALUE_MISSING", status=400)
    if op == "BETWEEN" and len(value) != 2:
        raise PcsError("BETWEEN 需要 [下界, 上界] 两个值",
                       code="REPORT_FILTER_VALUE_MISSING", status=400)
    return value


def _build_condition(cond: dict):
    # 嵌套组：带 conditions 的就是 AND/OR 分组，递归下去。
    # 判据是「有没有 conditions 键」而不是「operator 是不是 AND/OR」——
    # 否则 AND 既要能当分组连接符（spec 顶层）又能当叶子操作符（不支持），
    # 两种身份混在一个键上，哪天 SPEC 加一个叫 AND 的算子就彻底乱。
    if "conditions" in cond:
        return apply_filters(cond)

    op = cond.get("operator")
    if op not in SUPPORTED_OPS:
        raise PcsError(
            f"不支持的过滤操作符：{op!r}。"
            f"支持 {len(SUPPORTED_OPS)} 个（SPEC §3.2.2(4)）。",
            code="REPORT_FILTER_OP_UNSUPPORTED", status=400,
        )
    source, field = cond["source"], cond["field"]
    value = _need_value(op, cond.get("value"))

    ds = _datasource(source)
    spec = ds.fields.get(field)
    if spec is None:
        # ⚠️ 不能让 `ds.fields[field]` 抛 KeyError —— 那是 500，
        # 而字段名来自用户定义（字段树），报 400 并列出可用字段才有排查价值。
        raise PcsError(
            f"字段 {source}.{field!r} 不在数据源注册表中。"
            f"可用字段：{', '.join(sorted(ds.fields))}",
            code="REPORT_FIELD_UNKNOWN", status=400,
        )

    # JSONB 子键：容器->>'key'（用 ->> 取文本，避免类型转换歧义）
    if spec.is_jsonb_key:
        container, key = _jsonb_col(source, field)
        target: Any = container.op("->>")(key)
    else:
        target = _column(source, field)

    if op == "IS_NULL":
        return target.is_(None)
    if op == "IS_NOT_NULL":
        return target.is_not(None)
    if op == "EQ":
        return target == value
    if op == "NEQ":
        return target != value
    if op == "GT":
        return target > value
    if op == "GTE":
        return target >= value
    if op == "LT":
        return target < value
    if op == "LTE":
        return target <= value
    if op == "IN":
        return target.in_(list(value))
    if op == "NOT_IN":
        return target.not_in(list(value))
    if op == "CONTAINS":
        return target.like(f"%{value}%")
    if op == "STARTS_WITH":
        return target.like(f"{value}%")
    if op == "ENDS_WITH":
        return target.like(f"%{value}")
    if op == "LIKE":
        # LIKE 的通配符由用户自己写，不转义 —— 否则 % 就没法用了
        return target.like(value)
    if op == "BETWEEN":
        lo, hi = value
        return target.between(lo, hi)
    raise PcsError(f"未实现的操作符：{op}", code="REPORT_FILTER_OP_UNSUPPORTED",
                   status=400)


def apply_filters(spec: dict | None):
    """把 `{operator: AND|OR, conditions: [...]}` 编译成参数化表达式。

    - 未知操作符 → `REPORT_FILTER_OP_UNSUPPORTED`（400），不静默忽略
    - 缺 value → `REPORT_FILTER_VALUE_MISSING`（400），**绝不返回恒真**
    - 字段不在注册表 → `REPORT_FIELD_UNKNOWN`（400）
    - 空条件组 → `sa.true()`（空过滤器 = 不筛，不是报错）
    """
    if not spec:
        return sa.true()
    joiner = spec.get("operator", "AND")
    if joiner not in ("AND", "OR"):
        raise PcsError(f"条件组操作符只能是 AND/OR，实得 {joiner!r}",
                       code="REPORT_FILTER_OP_UNSUPPORTED", status=400)
    conds = [_build_condition(c) for c in spec.get("conditions", [])]
    if not conds:
        return sa.true()
    return sa.and_(*conds) if joiner == "AND" else sa.or_(*conds)


def build_select(source: str, fields: list[str]):
    """构造 `SELECT <列> FROM <模型>`。

    用 Core `select(...)` 返回 **tuple**，不用 ORM 实例 —— 10000 行时
    ORM 实体构造的开销是数量级差别（多源组装尤其明显）。
    """
    ds = _datasource(source)
    model = _model_for(ds)
    cols = []
    for f in fields:
        spec = ds.fields.get(f)
        if spec is None:
            raise PcsError(
                f"字段 {source}.{f} 不在数据源注册表中。",
                code="REPORT_FIELD_UNKNOWN", status=400)
        if spec.is_jsonb_key:
            container, key = _jsonb_col(source, f)
            cols.append(container.op("->>")(key).label(f))
        else:
            cols.append(_column(source, f))
    if not cols:
        raise PcsError(f"数据源 {source} 未选择任何字段",
                       code="REPORT_FIELD_UNKNOWN", status=400)
    return sa.select(*cols).select_from(model)


def apply_sort(stmt, sort_by: list[str]):
    """排序字段同样走注册表校验。顺序敏感：`sort_by` 即优先级。"""
    for f in sort_by:
        stmt = stmt.order_by(_column_from_label(stmt, f))
    return stmt


def _column_from_label(stmt, field: str):
    """从已 SELECT 的列里按 label 找排序目标。

    只认 `build_select` 产出的列 —— 排序目标必须是用户**已经选出来**的字段，
    否则又是一条能绕过 `build_select` 校验的旁路。
    """
    for c in stmt.selected_columns:
        if c.name == field:
            return c
    raise PcsError(
        f"排序字段 {field!r} 不在已选字段中 —— 排序目标必须先被 select。",
        code="REPORT_FIELD_UNKNOWN", status=400)


def paginate(stmt, *, limit: int, offset: int = 0):
    return stmt.limit(limit).offset(offset)


# --- 多源组装（用户 2026-10-09 裁决）---------------------------------------


def check_joins(sources: list[str]) -> list[tuple[str, str, str, str]]:
    """校验多源组合是否在白名单内，返回 `(a源, a键, b源, b键)` 列表。

    **只校验，不生成 SQL JOIN** —— 这是裁决的核心。白名单的作用是拒绝
    不在其中的关联，不是构造 JOIN 子句。
    """
    out = []
    for i, a in enumerate(sources):
        for b in sources[i + 1:]:
            a_key, b_key = join_key_for(a, b)     # 不在白名单会抛 400
            out.append((a, a_key, b, b_key))
    return out


def assemble(rows_by_source: dict[str, list[dict]],
             join_keys: list[tuple[str, str, str, str]],
             primary: str,
             fields_by_source: dict[str, list[str]],
             batch_size: int = 10000) -> list[dict]:
    """在 Python 里把多源结果组装成一张表。

    主源（`primary`）的每一行就是结果的一行；从源的列以 `{源}.{字段}` 为键
    挂上去，从源没匹配上就是**缺键**（不是 None —— None 是「值真的为空」，
    缺键是「这行没关联到」，两者在导出时含义不同）。

    四条实现约束（用户 2026-10-09 裁决）：
    1. 从源用 `WHERE key IN (...)` **一次批量查**（`fetch_join_rows`），不是 N 次
    2. Core 返回 tuple 不用 ORM 实例（见 `build_select`）
    3. **dict lookup 关联，不写嵌套循环**
    4. 行数超 `batch_size` → `REPORT_JOIN_TOO_LARGE`（400），不是静默截断

    纯函数：不碰 DB，好测。真查在 `fetch_join_rows`。
    """
    base_rows = rows_by_source.get(primary, [])
    if len(base_rows) > batch_size:
        raise PcsError(
            f"主源 {primary} 返回 {len(base_rows)} 行，超过 batch_size={batch_size}。"
            f"**不静默截断** —— 用户会拿到一份少了几千行的报表却毫无察觉。",
            code="REPORT_JOIN_TOO_LARGE", status=400,
        )

    # 先给每个从源建一张 {关联键: 行} 索引 —— 建一次、查 N 次，而不是每行重扫
    indexes: dict[str, dict[Any, dict]] = {}
    for _a, _a_key, b, b_key in join_keys:
        if b not in rows_by_source or b in indexes:
            continue
        # 重复关联键：取最后一条（与 SQL JOIN 的行为一致，且 dict 天然只留一条）
        indexes[b] = {row.get(b_key): row for row in rows_by_source[b]}

    out: list[dict] = []
    for base in base_rows:
        merged = dict(base)
        for a, a_key, b, b_key in join_keys:
            if b not in indexes:
                continue
            if a != primary:
                # 多跳链（A→B→C）不在首批 5 对白名单里，遇到了要看得见，
                # 不能静默跳过 —— 那会少拼几列而用户毫无察觉。
                logger.warning("assemble 跳过非主源起跳的 JOIN：%s.%s = %s.%s",
                               a, a_key, b, b_key)
                continue
            match = indexes[b].get(merged.get(a_key))
            if match is None:
                continue          # 没关联上 → 缺键，不写 None
            for f in fields_by_source.get(b, []):
                merged[f"{b}.{f}"] = match.get(f)
        out.append(merged)
    return out
