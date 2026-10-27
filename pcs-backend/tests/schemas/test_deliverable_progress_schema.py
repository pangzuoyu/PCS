"""交付物聚合进度段的 schema 契约（P9B-2 · 延后的 minor · Batch E）。

## 为什么 `available=false` 时 `reason` 必填

段的 `available` 字段的文档写的是「false 时 reason 必填，**不得返回空数组
冒充「无步骤」**」⇒ 「不可用」与「可用但一个节点都没有」在界面上**长得一样**
⇒ 前端只能靠 `reason` 区分 ⇒ **`reason` 缺失 = 前端把「这类流程不存在」
显示成「这条流程一个节点都没有」** ⇒ 用户读成「流程没走」。

⚠️ 此前 `reason` 只是 `str | None = None` ⇒ **契约允许**这个非法状态 ⇒
后端一旦漏填，前端**静默**降级 ⇒ 没人发现。

⇒ 把它钉进 **schema**（不是文档）：`available=false` 且 `reason` 为空 ⇒
**校验失败** ⇒ 服务端当场炸，而不是把坏数据发给前端。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.deliverable_progress import WorkflowProgressSection


def test_unavailable_section_requires_reason() -> None:
    """`available=false` + 空 `reason` ⇒ **校验失败**（不得静默通过）。"""
    with pytest.raises(ValidationError):
        WorkflowProgressSection(
            workflow_type="SIGN",
            workflow_id=None,
            available=False,
            reason=None,
        )


def test_unavailable_section_requires_non_blank_reason() -> None:
    """空串 / 纯空白**不算**理由（前端显示出来就是一片空白）。"""
    with pytest.raises(ValidationError):
        WorkflowProgressSection(
            workflow_type="SIGN",
            workflow_id=None,
            available=False,
            reason="   ",
        )


def test_available_section_may_have_no_reason() -> None:
    """`available=true` ⇒ `reason` 可以是 `None`（后端就这么写）。"""
    section = WorkflowProgressSection(
        workflow_type="SIGN",
        workflow_id="00000000-0000-0000-0000-000000000002",
        available=True,
        reason=None,
    )
    assert section.reason is None
