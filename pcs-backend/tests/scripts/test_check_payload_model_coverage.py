"""覆盖率闸 check_payload_model_coverage 的测试.

对应 spec/PCS 本体论与语义关系研究说明（V1.6）§3.4 约束①②③.

锁死三件事:
1. 未登记的表只算「欠账」, 不阻断（否则第一天就几百条红, 闸会被整体关掉）
2. 登记了但模型不存在 / description 与 ORM comment 不一致 → 阻断
3. 覆盖率不得低于基线（只拦倒退）

契约全文见 docs/PCS-NOTE-3.4-描述文本契约-2026-10-07.md.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "scripts"
    / "check_payload_model_coverage.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_payload_model_coverage", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    # 必须先注册进 sys.modules：脚本在 `from __future__ import annotations` 下
    # 用了 @dataclass，dataclasses 解析字符串注解时要回查 sys.modules[cls.__module__]，
    # 否则报 'NoneType' object has no attribute '__dict__'
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_unregistered_tables_are_debt_not_violations():
    """未登记 = 欠账, 不阻断. 闸只拦已登记项被改坏."""
    mod = _load_module()
    # 现存 29 张 *_result(s) 表几乎都未登记 —— 闸此刻必须是绿的
    result = mod.check()
    assert result.violations == [], result.violations
    assert result.debt_tables, "应报告出欠账表, 否则闸无声无息"


def test_debt_is_counted_per_table_with_json_payload():
    """欠账只统计真正有 JSON 载荷的 *_result(s) 表（无 JSON 列的表不算）."""
    mod = _load_module()
    result = mod.check()
    assert result.total_tables > 0
    # 覆盖率恒等于「登记且比对通过」的项数，不会超过表数
    assert 0 <= result.covered <= result.total_tables
    assert result.covered <= result.registered
    # 每张欠账表都真的有 JSON 列（否则它不该进这个口径）
    tables = mod._result_tables()
    for t in result.debt_tables:
        assert tables[t], f"{t} 没有 JSON 列，不该计为欠账"


def test_both_sides_of_the_contract_are_measured():
    """约束② 有两端，闸必须同时度量：载荷模型 + ORM comment 本身."""
    mod = _load_module()
    r = mod.check()
    assert r.json_columns > 0
    assert 0 < r.columns_with_comment < r.json_columns, (
        "实测 ORM comment 只覆盖约一半 JSONB 列 —— 这是约束② 落地前必须知道的事实，"
        "闸要把它显式报出来，而不是等对比失败才发现"
    )


def test_missing_model_is_a_violation():
    """登记表指向不存在的模型 → 违规."""
    mod = _load_module()
    violations = mod.check_entry(
        table="pump_results", column="output_json", target="app.schemas.nonexistent:Nope"
    )
    assert violations and "不存在" in violations[0]


def test_description_mismatch_is_a_violation():
    """已登记模型的 description 与 ORM comment 不一致 → 违规."""
    mod = _load_module()
    # 用一个真实存在的模型, 但故意写一个必然不等的 description
    violations = mod.check_entry(
        table="cost_est_results",
        column=None,
        target="app.schemas.cost_est:CostEstCalcBase",
        expect_description="绝对不可能与 ORM comment 逐字相等的字符串",
    )
    assert violations and "不一致" in violations[0]


def test_matching_description_passes():
    """登记正确时不得误报."""
    mod = _load_module()
    actual = mod.describe("app.schemas.cost_est:CostEstCalcBase")
    assert actual is not None
    assert mod.check_entry(
        table="cost_est_results", column=None,
        target="app.schemas.cost_est:CostEstCalcBase",
        expect_description=actual,
    ) == []


def test_registered_but_comment_drift_is_caught():
    """ORM comment 被改后, 已登记项必须报不一致."""
    mod = _load_module()
    # 用一个 comment 确实存在的列（heat_results.shell_params）；
    # 该表多数 JSONB 列的 comment 是 None —— 换个列会得到 None，测不出漂移
    comment = mod.orm_comment("heat_results", "shell_params")
    assert comment is not None, "前提：该列必须有 ORM comment"
    assert mod.check_entry(
        table="heat_results", column="shell_params",
        target="app.schemas.cost_est:CostEstCalcBase",
        expect_description=comment + " （被人动过）",
    )


def test_empty_orm_comment_is_reported_not_silently_passed():
    """ORM comment 为空时必须报出来，不能当成『一致』."""
    mod = _load_module()
    violations = mod.check_entry(
        table="heat_results", column="output_json",
        target="app.schemas.cost_est:CostEstCalcBase",
    )
    assert violations and "comment 为空" in violations[0]


def test_baseline_is_not_exceeded():
    """当前真实仓库跑闸必须是绿的（覆盖率不低于基线）."""
    mod = _load_module()
    assert mod.main() == 0


def test_exits_1_when_a_registered_entry_is_broken():
    """已登记项被改坏 → 阻断.

    注意不能靠「清空登记表」来模拟倒退：登记表本就为空，清空后覆盖率仍是 0，
    不会掉 —— 那样测的是个不存在的场景。真实的倒退是**已登记项被改坏**。
    """
    mod = _load_module()
    saved = dict(mod.REGISTRY)
    try:
        # 登记一个 description 必然对不上的项 → 闸必须阻断。
        # 「登记正确时是绿的」由 test_matching_description_passes 覆盖 ——
        # 真仓库里目前不存在能通过的登记（那正是 0% 覆盖的事实）。
        assert mod.orm_comment("heat_results", "shell_params") is not None
        mod.REGISTRY["heat_results"] = (
            "shell_params",
            "app.schemas.cost_est:CostEstCalcBase",
        )
        assert mod.main() == 1, "description 不等时应阻断"
    finally:
        mod.REGISTRY.clear()
        mod.REGISTRY.update(saved)
        assert mod.main() == 0, "恢复后必须回到绿"
