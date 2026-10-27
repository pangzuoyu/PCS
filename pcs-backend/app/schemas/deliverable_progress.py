"""交付物工作流进度聚合响应（TODO-065 · P9B-2 · T0）。

## 为什么每段都带 `available` + `reason`

空数组会被读成「这条流程一个节点都没有」，而真相是「这类工作流对本交付物
不存在」—— 两者在界面上**长得一样**（`workflow_progress.py:65` 已为单条端点
写过同样的警告：未知工作流 ⇒ 404，**不是** 空数组）。

⇒ 每段显式给 `available`；`available=false` 时 `reason` **必填**（中文原文，
前端原样显示）。

## 两类工作流的 `workflow_id` 语义（2026-10-27 复核）

| 工作流 | workflow_id | 依据（`deliverable_service.py` 的 grep 锚） |
|---|---|---|
| SIGN | 版本 id | `workflow_type=WorkflowType.SIGN`（`sign_step`） |
| CUSTOMER_APPROVAL_PROXY | **交付物 id** | `workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY` |

⚠️ **P9B-1 计划写的是「CUSTOMER_APPROVAL_PROXY → 版本 ID」，与代码不符** ——
本实现按**代码**（R-2），并同步修订 `TODOS.md` TODO-065 的那张表。

⚠️ **`CHANGE_NOTICE` 段已删**（R-13）：变更单自己是交付物 ⇒ 它在进度页上
自己一行；而 `Deliverable.parent_deliverable_id` **全仓从未被写** ⇒ 靠它反查
变更单**永远查不到** ⇒ 留着一个**永远为假**的段比没有更坏（用户会以为是
数据问题）。
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, model_validator

from app.schemas.workflow_progress import WorkflowProgressItemResponse


class WorkflowProgressSection(BaseModel):
    """一类工作流在本交付物上的进度。"""

    workflow_type: str = Field(
        description="SIGN / CUSTOMER_APPROVAL_PROXY（R-13：CHANGE_NOTICE 段已删）"
    )
    workflow_id: uuid.UUID | None = Field(
        default=None,
        description="该类工作流的主键；不可用时为 null",
    )
    available: bool = Field(
        description=(
            "该类工作流是否可解析（false 时 reason 必填，"
            "不得返回空数组冒充「无步骤」）"
        )
    )
    reason: str | None = Field(
        default=None,
        description="available=false 时的原因（中文原文，前端原样显示）",
    )
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    items: list[WorkflowProgressItemResponse] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reason_required_when_unavailable(self) -> WorkflowProgressSection:
        """`available=false` ⇒ `reason` **必填**（钉进契约，不靠自觉）。

        ⚠️ 「不可用」与「可用但一个节点都没有」在界面上**长得一样** ⇒ 前端只
        能靠 `reason` 区分 ⇒ `reason` 缺失 ⇒ 用户把「这类流程不存在」读成
        「流程一个节点都没有」⇒ **静默降级**。

        ⚠️ 校验失败会让响应变成 500（而不是把坏数据发给前端）—— 这是**故意**
        的：能构造出这种段的服务端代码有 bug，服务端当场炸比前端静默降级好。
        """
        if not self.available and not (self.reason or "").strip():
            raise ValueError(
                "available=false 时 reason 必填（不得返回空数组冒充「无步骤」）"
            )
        return self


class DeliverableProgressResponse(BaseModel):
    """一个交付物的两类工作流进度（R-13：CHANGE_NOTICE 段已删）。"""

    deliverable_id: uuid.UUID
    sections: list[WorkflowProgressSection]
