"""血缘图的契约（**具名 schema**）—— P9B-4 T0-D（TODO-136 · TODO-111 的一半）。

## 为什么要有这个文件

血缘 graph 端点此前是 `response_model=dict`（**裸 dict**）⇒ 契约里**没有任何
字段说明** ⇒ 前端只能**手写**一份 `LineageGraph`（`src/api/stream.ts`）⇒
后端加字段 / 改语义，前端**静默失配**。

⚠️ 本文件存在的主要理由是**两套词表**（`source` 有两个互不相同的含义）：

- **合成 root**（`record_type='streams'` 入口）⇒ `source` = 物流**怎么进系统的**
  ⇒ 词表：`MANUAL` / `SIM_IMPORT` / `EXCEL` / `LAB`；
- **血缘节点**（`upstream` / `downstream`）⇒ `source` = 记录**怎么算出来的**
  ⇒ 词表：`CALC` 等。

⇒ 语义不同 ⇒ 前端**不得混用** ⇒ 靠本文件的 `description` 写清楚。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

__all__ = ["LineageNode", "LineageRoot", "LineageGraphResponse"]


class LineageNode(BaseModel):
    """血缘节点（一条 `data_lineage` 行）。

    ⚠️ `source` = **计算来源**（`CALC` 等）——「这条记录是怎么算出来的」。
    """

    lineage_id: uuid.UUID = Field(
        ..., description="血缘行 id（`data_lineage.lineage_id`）"
    )
    record_type: str = Field(
        ..., description="记录类型（**类名**，如 `PipingResult`）—— 不是 registry 的键"
    )
    record_id: str = Field(..., description="记录 id（该记录类型的主键）")
    parent_lineage_id: str | None = Field(
        None, description="父血缘行 id（版本链的上一环）"
    )
    source: str | None = Field(
        None, description="**计算来源**（`CALC` 等）——「这条记录是怎么算出来的」"
    )
    source_ref_type: str | None = Field(
        None, description="上游引用**类型**（如 `Stream`）"
    )
    source_ref_id: str | None = Field(None, description="上游引用**id**")
    actor_user_id: str | None = Field(None, description="操作人 user_id")
    change_summary: str | None = Field(None, description="变更摘要")
    occurred_at: datetime | None = Field(None, description="发生时间（ISO 8601）")


class LineageRoot(LineageNode):
    """血缘图的 **root**。

    ⚠️ **root 的 `source` 与节点的 `source` 语义不同**：

    - **`record_type='streams'` 入口** ⇒ root 是**合成**的（`data_lineage` 表里
      **没有**这一行）⇒ 它的 `source` = **物流来源**（录入通道）
      （`MANUAL` / `SIM_IMPORT` / `EXCEL` / `LAB`）——「物流怎么进系统的」；
    - **其它入口** ⇒ root 是一条真实血缘行 ⇒ 它的 `source` 与节点**相同**
      （计算来源）。

    ⇒ 两套词表**语义不同** ⇒ 前端**不得混用**（血缘 Tab 的「来源」列要区分）。
    """

    source: str | None = Field(
        None,
        description=(
            "**root 的 source 是物流来源**（MANUAL / SIM_IMPORT / EXCEL / LAB）；"
            "**节点的 source 是计算来源**（CALC 等）⇒ 两者语义不同，前端不得混用。"
            "对非 `streams` 入口，root 的 source 与节点相同。"
        ),
    )


class LineageGraphResponse(BaseModel):
    """血缘图 —— `{root, upstream, downstream}` **三键**（形状不变）。

    ⚠️ 键名与顺序沿用既有契约（前端 `src/api/stream.ts` + `StreamLineageTab`
    的 `toRows` 依赖这三个键）⇒ **不要**改成 `{root, nodes}`。
    """

    root: LineageRoot | None = Field(
        None, description="根节点（`streams` 入口下是**合成**的，DB 里没有这一行）"
    )
    upstream: list[LineageNode] = Field(
        default_factory=list, description="上游血缘链（由近及远）"
    )
    downstream: list[LineageNode] = Field(
        default_factory=list, description="下游血缘链（由近及远）"
    )
