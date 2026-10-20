"""记录能力谓词（TODO-058 裁决，2026-10-20）。

## 裁决：`RECORD_TYPE_REGISTRY` 是**表枚举**，不是能力清单

实测（2026-10-20）：`RECORD_TYPE_REGISTRY` 在 `app/` 里的**唯一代码消费方**
是 `api/v1/records_actions.py`（P9A B lane 新写）；其余引用全是模型注释与
`tests/architecture/*` 里的存在性断言（`len == 21`、`"X" in REGISTRY`）。
它原本被设想成 `finalize_calc_record` 的支持清单（ADR-0031 / P4-TASK0），
但那是**鸭子类型**实现的，注册表从未真的驱动过它（见 TODO-048）。

所以「注册表里为什么有 `CostEstResult` / `TwoPhaseResult` /
`ProjectCalculationStandardProfile`」的答案是：**它们是结果表，所以被登记了。**
这三张表实测各缺 24 个 `RecordMixin` 列（`CostEstResult` 缺 25）——
它们**根本不继承 `RecordMixin`**，不是记录。

⇒ 「能不能走 9 态工作流」是一个**从 schema 推导的谓词**，不是注册表的属性。

## 为什么不给它建第二份清单

「可工作流模块清单」看起来更直白，但它是**人工维护的事实**，
而注册表也是人工维护的事实 —— 两份必然漂移，而漂移的那份没人会去对。
本仓已经为「第二份清单」付过代价：P9A B lane 明确拒绝另建
「模块 → 模型」映射而复用注册表；终审的 CRITICAL（23 条 RED）也正源于
「注册表是能力清单」这个未经证实的假设被当成了保护色。

谓词从 mixin 派生 ⇒ **推导出来的，不漂移**。

## 例外字典是什么

`WORKFLOW_UNSUPPORTED` 记录**当前**不支持工作流的键 + **为什么**。
它不是第二份清单（不新增键，只解释已存在的键），且测试强制每条理由
必须提到该键**真实缺失的列** —— 写「该表不参与工作流」这种空话会红。

某天 `CostEstResult` 补上了 `project_id` 与 `sign_status`（D lane 的
`cost_est_results.record_hash` 是第一步），把它的条目删掉即可；
`test_supported_keys_are_not_listed_as_exceptions` 会确保不出现
「已支持却还列在例外里」的僵尸条目。
"""
from __future__ import annotations

from typing import Any

from app.models.mixins import RecordMixin
from app.services.calc_lineage import RECORD_TYPE_REGISTRY

#: 9 态工作流所依赖的列 = `RecordMixin` 的全部列 + `project_id`。
#: **从 mixin 自己派生**而不是手抄：手抄的清单会与 mixin 漂移，而漂移的表现是
#: 「哪天给 mixin 加了列、判定却没跟着变」—— 于是又出现一条
#: 「模块解析成功但加载 500」的路（P9A 终审 CRITICAL 的成因）。
REQUIRED_WORKFLOW_COLUMNS: frozenset[str] = frozenset(RecordMixin.__annotations__) | {
    "project_id"
}

#: 注册表里**当前**不支持 9 态工作流的键 + 真实原因。
#: 理由必须点名它实际缺的列（测试强制），否则会被读成一句正确的废话。
WORKFLOW_UNSUPPORTED: dict[str, str] = {
    "CostEstResult": (
        "独立的成本估算表，不继承 RecordMixin：缺 project_id / sign_status / "
        "record_hash 等 25 列。D lane 的 cost_est_results.record_hash 是补齐的第一步。"
    ),
    "TwoPhaseResult": (
        "两相流结果表，不继承 RecordMixin：缺 project_id / sign_status 等 24 列。"
        "（它的 record_hash **是**存在的 —— 模型注释「TwoPhaseResult 无 record_hash 列」"
        "不成立，见 TODO-049。）"
    ),
    "ProjectCalculationStandardProfile": (
        "项目计算标准档案（P5-0-5），是**配置**不是计算结果：缺 sign_status / "
        "approval_* / record_hash 等 24 列，故不参与签署与撤销。"
        "但它**有 project_id**，所以可以被批注（批注只需要归属项目）。"
    ),
}


def missing_workflow_columns(model: Any) -> list[str]:
    """该模型缺哪些工作流所需的列（空 = 支持）。**报出来，不吞掉。"""
    columns = set(model.__table__.columns.keys())
    return sorted(REQUIRED_WORKFLOW_COLUMNS - columns)


def supports_state_workflow(model: Any, *, need_workflow: bool = True) -> bool:
    """这条记录能不能走 9 态工作流（签署 / 撤销 / 变更 / 撤销申请 / 批注以外的写面）。

    Args:
        model: ORM 模型类。
        need_workflow: False = 只需要 `project_id`（批注：任何有归属项目的
            「记录」都能留言，不必具备状态机列）。

    ⚠️ 调用方**不要**再自带一份「支持哪些模块」的清单 —— 那就是第二真相源。
    要限制用户能操作什么，用 `WORKFLOW_UNSUPPORTED` 里的**理由**去写错误文案。
    """
    columns: Any = set(model.__table__.columns.keys())
    if not need_workflow:
        return "project_id" in columns
    return REQUIRED_WORKFLOW_COLUMNS <= columns


__all__ = [
    "RECORD_TYPE_REGISTRY",
    "REQUIRED_WORKFLOW_COLUMNS",
    "WORKFLOW_UNSUPPORTED",
    "missing_workflow_columns",
    "supports_state_workflow",
]
