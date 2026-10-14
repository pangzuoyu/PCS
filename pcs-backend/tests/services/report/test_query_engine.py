"""取数引擎契约 —— 过滤/排序/字段选择/NULL 处理的**唯一实现**。

三条要害：

1. **15 个操作符全参数化**（SPEC §3.2.2(4)）—— 任何一处 f-string 拼值就是注入面。
2. **缺 value 绝不静默放行** —— `{"operator":"IS_NULL"}` 没 value 时被忽略掉
   会**返回全表**，比报错危险得多（Review Focus #3）。
3. **字段名必须存在于 datasource_registry** —— 防注入之外，还防幻觉列：
   字段树里存了个不存在的列名时，这里拦住而不是让用户拿到 500。
"""
from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from app.services.exceptions import PcsError
from app.services.report.query_engine import (
    SUPPORTED_OPS,
    apply_filters,
    apply_sort,
    assemble,
    build_select,
    check_joins,
)

OPS = ["EQ", "NEQ", "GT", "GTE", "LT", "LTE", "IN", "NOT_IN", "CONTAINS",
       "STARTS_WITH", "ENDS_WITH", "IS_NULL", "IS_NOT_NULL", "BETWEEN", "LIKE"]


def _spec(op: str, value=None, **kw):
    cond = {"source": "EQUIP_LIST", "field": "vendor", "operator": op}
    if value is not None:
        cond["value"] = value
    cond.update(kw)
    return {"operator": "AND", "conditions": [cond]}


def _sql(expr) -> str:
    return str(expr.compile(dialect=postgresql.dialect(),
                            compile_kwargs={"literal_binds": False}))


def test_all_fifteen_operators_implemented():
    """SPEC §3.2.2(4) 是 15 个操作符，少一个就是功能缺口。"""
    assert sorted(SUPPORTED_OPS) == sorted(OPS)


@pytest.mark.parametrize("op", OPS)
def test_operator_translates_to_parameterized_sql(op):
    """**全部走参数化** —— 值必须进 bind params，不能进 SQL 文本。"""
    value = ["a", "b"] if op in ("IN", "NOT_IN") else \
        ([1, 10] if op == "BETWEEN" else "X")
    cond = apply_filters(_spec(op, value))
    sql = _sql(cond)
    assert "X" not in sql and "'a'" not in sql, f"值泄漏进 SQL 文本：{sql}"
    assert cond is not None


def test_is_null_has_no_value():
    """IS_NULL / IS_NOT_NULL 不带 value，SQL 必须是 `IS NULL` 而不是 `IS  NULL`。"""
    assert "IS NULL" in _sql(apply_filters(_spec("IS_NULL")))


@pytest.mark.parametrize("op", [o for o in OPS if o not in ("IS_NULL", "IS_NOT_NULL")])
def test_missing_value_raises_instead_of_returning_everything(op):
    """**Review Focus #3**：缺 value 被忽略掉会返回全表，比报错危险得多。

    这个断言是本文件最重要的一条 —— 它区分「报错」与「静默放行」。
    """
    with pytest.raises(PcsError) as e:
        apply_filters(_spec(op))          # 故意不给 value
    assert e.value.code == "REPORT_FILTER_VALUE_MISSING"


def test_between_requires_two_element_list():
    with pytest.raises(PcsError) as e:
        apply_filters(_spec("BETWEEN", [1]))
    assert e.value.code == "REPORT_FILTER_VALUE_MISSING"


def test_in_requires_list():
    with pytest.raises(PcsError) as e:
        apply_filters(_spec("IN", "notalist"))
    assert e.value.code == "REPORT_FILTER_VALUE_MISSING"


def test_unknown_operator_raises_not_ignored():
    """未知操作符**不静默忽略** —— 静默忽略等于用户以为筛了其实没筛。"""
    with pytest.raises(PcsError) as e:
        apply_filters(_spec("DROP_TABLE", "x"))
    assert e.value.code == "REPORT_FILTER_OP_UNSUPPORTED"
    assert e.value.status == 400


def test_unknown_field_raises_not_sql_error():
    """字段名必须在 registry 里 —— 幻觉列在这里拦住，不留给运行时 500。"""
    with pytest.raises(PcsError) as e:
        apply_filters(_spec("EQ", "X", field="vendor; DROP TABLE equipment_list"))
    assert e.value.code == "REPORT_FIELD_UNKNOWN"


def test_injection_attempt_returns_params_not_raises():
    """注入串当**值**时正常进 bind params，不抛异常、不改语义。"""
    cond = apply_filters(_spec("EQ", "'; DROP TABLE equipment_list; --"))
    assert "DROP TABLE" not in _sql(cond)
    assert cond is not None


def test_and_or_grouping_nests():
    """AND/OR 分组可嵌套（SPEC §3.2.2(4)）。"""
    spec = {"operator": "OR", "conditions": [
        _spec("EQ", "A")["conditions"][0],
        {"operator": "AND", "conditions": [
            _spec("NEQ", "B")["conditions"][0],
            _spec("CONTAINS", "C")["conditions"][0],
        ]},
    ]}
    assert _sql(apply_filters(spec))


def test_empty_conditions_returns_true_not_nothing():
    """无条件组返回「恒真」表达式 —— 空过滤器不筛任何东西，不是不筛就报错。"""
    assert _sql(apply_filters({"operator": "AND", "conditions": []})) == "true"


def test_sort_uses_column_not_string_concat():
    """排序字段同样走 registry 校验，且不拼字符串进 ORDER BY。"""
    stmt = apply_sort(build_select("EQUIP_LIST", ["vendor"]), ["vendor"])
    assert "ORDER BY" in str(stmt)
    with pytest.raises(PcsError):
        apply_sort(build_select("EQUIP_LIST", ["vendor"]), ["vendor; --"])


def test_build_select_rejects_field_outside_registry():
    with pytest.raises(PcsError) as e:
        build_select("EQUIP_LIST", ["vendor", "no_such_column"])
    assert e.value.code == "REPORT_FIELD_UNKNOWN"


def test_build_select_rejects_unknown_datasource():
    with pytest.raises(PcsError) as e:
        build_select("NOT_A_SOURCE", ["vendor"])
    assert e.value.code == "REPORT_DATASOURCE_UNKNOWN"

# --- 多源组装（用户 2026-10-09 裁决：Python 组装，不生成 SQL JOIN）----------


def test_check_joins_validates_against_whitelist():
    keys = check_joins(["EQUIP_LIST", "PUMP_RESULTS"])
    assert keys == [("EQUIP_LIST", "tag_number", "PUMP_RESULTS", "tag_number")]


def test_check_joins_rejects_unlisted_combination():
    with pytest.raises(PcsError) as e:
        check_joins(["EQUIP_LIST", "STREAMS"])
    assert e.value.code == "REPORT_BUILDER_JOIN_NOT_SUPPORTED"


def test_check_joins_generates_no_sql():
    """白名单只用于**校验** —— 裁决明说「不生成 JOIN SQL」。"""
    sql = str(check_joins(["EQUIP_LIST", "PUMP_RESULTS"]))
    for banned in ("JOIN", "SELECT"):
        assert banned not in sql


def test_assemble_merges_via_dict_lookup():
    base = [{"tag_number": "P-101", "vendor": "ACME"},
            {"tag_number": "P-102", "vendor": "ACME"}]
    pumps = [{"tag_number": "P-101", "actual_head": 32.0}]
    rows = assemble(
        rows_by_source={"EQUIP_LIST": base, "PUMP_RESULTS": pumps},
        join_keys=[("EQUIP_LIST", "tag_number", "PUMP_RESULTS", "tag_number")],
        primary="EQUIP_LIST",
        fields_by_source={"PUMP_RESULTS": ["actual_head"]})

    assert len(rows) == 2
    assert rows[0]["PUMP_RESULTS.actual_head"] == 32.0
    # 没关联上 → **缺键**，不是 None（None 是「值真的为空」，缺键是「没关联到」）
    assert "PUMP_RESULTS.actual_head" not in rows[1]


def test_assemble_does_not_mutate_input_rows():
    """组装返回新 dict —— 复用同一批行查多个组合时，污染输入会串味。"""
    base = [{"tag_number": "P-101"}]
    assemble({"EQUIP_LIST": base, "PUMP_RESULTS": [{"tag_number": "P-101", "actual_head": 1.0}]},
             [("EQUIP_LIST", "tag_number", "PUMP_RESULTS", "tag_number")],
             "EQUIP_LIST", {"PUMP_RESULTS": ["actual_head"]})
    assert base == [{"tag_number": "P-101"}]


def test_assemble_raises_when_over_batch_size_not_silently_truncating():
    """超批量**报错**不截断 —— 静默截断 = 用户拿到少几千行的报表却不知情。"""
    rows = [{"tag_number": f"P-{i}"} for i in range(11)]
    with pytest.raises(PcsError) as e:
        assemble({"EQUIP_LIST": rows}, [], "EQUIP_LIST", {}, batch_size=10)
    assert e.value.code == "REPORT_JOIN_TOO_LARGE"
    assert e.value.status == 400


def test_assemble_is_linear_not_nested_loop():
    """dict lookup 的意义就在复杂度。

    ⚠️ 第一版这个测试是**假绿**：我用 `CountingRow.__getitem__` 计数，而嵌套
    循环实现用的是 `r.get(b_key)` —— 根本没走 `__getitem__`，计数恒为 0，
    把 dict lookup 换成 `next(... for r in rows...)` 照样全绿。是变异测试
    抓出来的，不是这个测试抓出来的。

    正确的观测点是**迭代**：嵌套循环对每个主源行都要把从源整个走一遍，
    dict lookup 只在建索引时走一遍。
    """
    class CountingList(list):
        def __init__(self, *a):
            super().__init__(*a)
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    base = [{"tag_number": f"P-{i}"} for i in range(100)]
    pumps = CountingList([{"tag_number": "P-101", "actual_head": 1.0}])
    assemble({"EQUIP_LIST": base, "PUMP_RESULTS": pumps},
             [("EQUIP_LIST", "tag_number", "PUMP_RESULTS", "tag_number")],
             "EQUIP_LIST", {"PUMP_RESULTS": ["actual_head"]})
    # 建索引 1 次。嵌套循环会对 100 个主源行各走 1 次从源 → 100 次。
    assert pumps.iterations <= 2, \
        f"从源被遍历 {pumps.iterations} 次 —— 是嵌套循环而不是 dict lookup"


async def _seed_tags(db, tags):
    """建项目 + 若干设备行（tag_number 是被排序的那一列）。"""
    import uuid

    from app.models.equipment import EquipmentList
    from app.models.project import Project

    pid = uuid.uuid4()
    db.add(Project(
        project_id=pid, project_no=f"S{pid.hex[:6]}", project_name="t",
        owner_company="t", location="t", project_type="test",
        design_phase="BASIC", unit_system="SI", status="ACTIVE",
        workspace_id=uuid.uuid4()))
    for tag in tags:
        db.add(EquipmentList(
            equipment_id=uuid.uuid4(), project_id=pid,
            workspace_id=uuid.uuid4(), type_code="PUMP",
            equipment_name="e", tag_number=tag))
    await db.flush()
    return pid


# --- 评审 P2 #9：SortBy 的 direction 被静默丢弃 -------------------------------
#
# `ReportDefSort` 有 `direction: str = "ASC"`（schema 层声明过），
# 而 `builder_service` 只取 `f["field"]`、`apply_sort` 也只 `order_by(col)` ——
# **direction 从来没被用过**。用户存 DESC，导出仍是升序，
# 且没有任何一层会说话：定义保存成功、执行成功、报表 200。

@pytest.mark.asyncio
async def test_sort_direction_desc_is_honoured(db):
    """`direction="DESC"` 必须真的倒序。"""
    from sqlalchemy import select

    from app.models.equipment import EquipmentList
    from app.services.report.query_engine import build_select

    await _seed_tags(db, ("A-3", "A-1", "A-2"))
    stmt = build_select("EQUIP_LIST", ["tag_number"])
    desc = apply_sort(stmt, [{"field": "tag_number", "direction": "DESC"}])
    rows = [r[0] for r in (await db.execute(desc)).all()]
    assert rows == sorted(rows, reverse=True), f"实得 {rows}"


@pytest.mark.asyncio
async def test_sort_direction_asc_is_the_default(db):
    """`direction="ASC"` 与不传等价（不传仍按老样子支持裸字符串）。"""
    from app.services.report.query_engine import build_select

    await _seed_tags(db, ("A-3", "A-1", "A-2"))
    asc = apply_sort(build_select("EQUIP_LIST", ["tag_number"]),
                     [{"field": "tag_number", "direction": "ASC"}])
    bare = apply_sort(build_select("EQUIP_LIST", ["tag_number"]), ["tag_number"])
    rows_asc = [r[0] for r in (await db.execute(asc)).all()]
    rows_bare = [r[0] for r in (await db.execute(bare)).all()]
    assert rows_asc == rows_bare == sorted(rows_asc), f"{rows_asc} vs {rows_bare}"


def test_an_unknown_direction_is_rejected_not_silently_ascending():
    """未知 direction 必须 400，**不能**当 ASC 处理。

    静默当升序 = 把「保存成功、执行时被忽略」换个地方重演一遍 ——
    用户存了 DESC 拿不到 DESC，且没有任何提示。
    """
    from app.services.exceptions import PcsError
    from app.services.report.query_engine import build_select

    with pytest.raises(PcsError) as ei:
        apply_sort(build_select("EQUIP_LIST", ["tag_number"]),
                   [{"field": "tag_number", "direction": "SIDEWAYS"}])
    assert ei.value.code == "REPORT_FIELD_UNKNOWN"
    # ⚠️ 必须断言**报错原因**：不写这条，这条测试在修复前也是绿的 ——
    # 因为 dict 条目会撞上「不在已选字段中」而抛同一个 code。
    # 那就是「因错误的原因通过」，与 bug-174 同族（断言没钉住要验的东西）。
    assert "direction" in str(ei.value), f"报错说的是别的事：{ei.value}"
