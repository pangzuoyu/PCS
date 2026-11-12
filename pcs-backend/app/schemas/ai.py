"""AI 预留接口的请求/响应 schema（P10-A · Task T9）。

## 为什么用**具名** schema 而不是裸 dict

仓的纪律：新增端点必须显式声明结构 ⇒ 字段名有**编译期**约束
（改字段名时类型检查器就会报错，而不是等运行时静默失效）。

## ⚠️ 两条「静默失效」的坑（已用别名堵住）

Pydantic v2 **默认忽略**未知字段 ⇒ 若请求体字段名与 schema 不一致，
前端传的值**静默变成默认值**，而且**不报错**。本仓已吃过同型亏：

| 字段 | SPEC 里的名字 | schema 里的名字 | 别名 |
|---|---|---|---|
| 知识库检索条数 | `topK` | `top_k` | `topK` |
| 上下文项目 id | `projectId` | `project_id` | `projectId` |
| 上下文记录 id | `recordId` | `record_id` | `recordId` |

⇒ 一律 `populate_by_name=True` ⇒ **驼峰与蛇形两种写法都能进**
（内部仍用蛇形）。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AiContext(BaseModel):
    """AI 请求的上下文（SPEC §4.1.1）。

    ⚠️ **驼峰别名**：`projectId` / `recordId`（SPEC 用驼峰）⇒ 不加别名
    的话 Pydantic 会**静默忽略**它们 ⇒ 前端传的上下文变 None。
    """

    model_config = ConfigDict(populate_by_name=True)

    project_id: str | None = Field(None, alias="projectId", description="项目 id")
    module: str | None = Field(None, description="模块名（如 PUMP）")
    record_id: str | None = Field(None, alias="recordId", description="记录 id")


class AiIntentRequest(BaseModel):
    """意图识别请求（SPEC §4.1.1）。"""

    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., description="自然语言指令")
    context: AiContext | None = Field(None, description="调用上下文")


class AiKnowledgeSearchRequest(BaseModel):
    """知识库检索请求（SPEC §4.1.2）。"""

    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., description="检索串")
    top_k: int = Field(5, alias="topK", description="返回条数")


class AiEquipmentRecommendRequest(BaseModel):
    """相似设备推荐请求（SPEC §3.1.2「设备推荐」）。

    ⚠️ SPEC 只给了端点与用途，**没给请求体** ⇒ 本仓定的最小形状
    （偏离登记 D17）。
    """

    model_config = ConfigDict(populate_by_name=True)

    equipment_tag: str | None = Field(None, description="已知设备位号")
    context: AiContext | None = Field(None, description="调用上下文")


class AiExplainRequest(BaseModel):
    """自然语言解释请求（SPEC §3.1.2「自然语言解释」）。"""

    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(..., description="待解释的内容 / 变更描述")
    context: AiContext | None = Field(None, description="调用上下文")


class AiDocumentExtractRequest(BaseModel):
    """文档解析请求（SPEC §3.1.2「文档解析」）。"""

    model_config = ConfigDict(populate_by_name=True)

    document_ref: str | None = Field(None, description="文档引用（规范号 / 文件 id）")
    context: AiContext | None = Field(None, description="调用上下文")
