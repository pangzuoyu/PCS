"""`record_capabilities` 测试（TODO-058 裁决的落地契约）。

## 裁决内容（2026-10-20）

`RECORD_TYPE_REGISTRY` 的语义定为 **「本仓的结果表模型清单」（表枚举）**，
**不是**「可参与工作流的记录类型」的能力清单。

「这条记录能不能走 9 态工作流」是**从 schema 推导的谓词**
（是否具备 `RecordMixin` 全列 + `project_id`），
**不是注册表的属性**，因此**不需要**第二份清单 ——
它是推导出来的，天然不会与注册表漂移；而人工维护的清单一定会漂移
（P9A B lane 已经为此付过一次代价：终审 CRITICAL 的 23 条 RED
就是「注册表里混着列不齐的表」被参数化测试剥出来的）。

这份测试钉住三件事：
1. 谓词本身正确（具备列的过、不具备的不过）；
2. **注册表里每个键要么支持、要么在例外字典里，且理由非空** ——
   新加一个「列不齐的表」却不登记原因，这里会红；
3. **理由必须针对该键真实缺失的列** ——
   防止写「该表不支持工作流」这种对任何键都成立的空话。
"""
from __future__ import annotations

import pytest

from app.db.base import Base
import app.models  # noqa: F401  触发全部 model 注册
from app.models.mixins import RecordMixin
from app.services.calc_lineage import RECORD_TYPE_REGISTRY
from app.services.record_capabilities import (
    WORKFLOW_UNSUPPORTED,
    missing_workflow_columns,
    supports_state_workflow,
)


class TestPredicate:
    def test_record_model_is_supported(self):
        from app.models.calc import PipingResult

        assert supports_state_workflow(PipingResult) is True
        assert missing_workflow_columns(PipingResult) == []

    def test_model_without_mixin_columns_is_not_supported(self):
        from app.models.calc import CostEstResult

        assert supports_state_workflow(CostEstResult) is False
        assert missing_workflow_columns(CostEstResult), "必须报出缺哪些列"

    def test_missing_columns_are_reported_not_swallowed(self):
        """「不支持」必须能回答「缺什么」——
        否则调用方（端点 / 前端）只能显示一句无信息量的「不支持」。"""
        from app.models.calc import TwoPhaseResult

        missing = missing_workflow_columns(TwoPhaseResult)
        assert "sign_status" in missing
        assert "project_id" in missing


class TestRegistryContract:
    def test_every_registry_key_is_either_supported_or_explained(self):
        """注册表的每个键都必须有明确归属。

        这是 TODO-058 的核心契约：**新往注册表加一张列不齐的表却不登记原因，
        这里会红** —— 而那正是 P9A 终审踩到的形状。
        """
        unexplained = [
            key
            for key, model in RECORD_TYPE_REGISTRY.items()
            if not supports_state_workflow(model) and key not in WORKFLOW_UNSUPPORTED
        ]
        assert not unexplained, (
            f"这些注册表键不支持 9 态工作流但未在 WORKFLOW_UNSUPPORTED 里说明原因：{unexplained}"
        )

    def test_exception_reasons_are_non_empty(self):
        for key, reason in WORKFLOW_UNSUPPORTED.items():
            assert key in RECORD_TYPE_REGISTRY, f"例外字典里的 {key} 不在注册表中"
            assert reason.strip(), f"{key} 的不支持原因是空的"

    def test_exception_reasons_name_real_missing_columns(self):
        """理由必须针对**该键真实缺的列**，不能是放之四海皆准的空话。

        实现方式：理由里必须出现该键实际缺失列中的至少一个。
        写「该表不参与工作流」这种话 → 这里红。
        """
        vacuous = []
        for key in WORKFLOW_UNSUPPORTED:
            model = RECORD_TYPE_REGISTRY[key]
            missing = set(missing_workflow_columns(model))
            reason = WORKFLOW_UNSUPPORTED[key]
            if not (missing & set(reason.replace("`", "").replace("/", " ").split())):
                vacuous.append(key)
        assert not vacuous, f"这些不支持原因没提到任何真实缺失的列：{vacuous}"

    def test_supported_keys_are_not_listed_as_exceptions(self):
        """两类不能重叠 —— 重叠说明例外字典被用来「掩盖」已支持的键。"""
        overlap = [
            key
            for key in WORKFLOW_UNSUPPORTED
            if supports_state_workflow(RECORD_TYPE_REGISTRY[key])
        ]
        assert not overlap, f"这些键其实支持工作流却列进了例外字典：{overlap}"

    def test_both_sides_of_the_partition_are_non_empty(self):
        """两边都不能空 —— 空集合说明判定写死了而不是真在推导。"""
        supported = [k for k, m in RECORD_TYPE_REGISTRY.items() if supports_state_workflow(m)]
        unsupported = [k for k in WORKFLOW_UNSUPPORTED]
        assert supported, "没有任何注册表键被判为支持工作流"
        assert unsupported, "没有任何键被判为不支持（分区可能写死了）"


class TestDerivationIsNotACopy:
    def test_required_columns_come_from_the_mixin_itself(self):
        """所需列**从 `RecordMixin` 派生**，不是手抄一份。

        手抄的清单会与 mixin 漂移；漂移的表现是「哪天给 mixin 加了列，
        这里的判定却没跟着变」—— 于是又出现一条「解析成功但加载 500」的路。
        """
        from app.services.record_capabilities import REQUIRED_WORKFLOW_COLUMNS

        assert set(RecordMixin.__annotations__) <= set(REQUIRED_WORKFLOW_COLUMNS)
        assert "project_id" in REQUIRED_WORKFLOW_COLUMNS

    def test_all_result_models_are_reachable_from_metadata(self):
        """`Base.metadata` 里的模型数 ≥ 注册表键数。

        防止「注册表漏了新表」：漏注册的表在工作流端点上表现为
        「这个模块不认识」，而用户看到的只是一个他刚建的数据类型。
        """
        tables = {t.name for t in Base.metadata.tables.values()}
        assert len(tables) > len(RECORD_TYPE_REGISTRY), (
            "注册表键数超过表数 —— 注册表里有指向不存在表的键？"
        )
