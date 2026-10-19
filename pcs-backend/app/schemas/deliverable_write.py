"""交付物写面 schema（P9A B1 `issue` 端点）。

与 `app/schemas/deliverable.py`（读面）分开：读面是 P8 的前置，写面是 P9 签署流程的
起点，两者演进节奏不同，且写面必须**显式声明响应模型**（P9A-DLV-010 零裸字段约束）。

## 为什么版本目的用 `Literal` 而不是 `str`

`deliverables.version_purpose` 是 `String(40)`，注释写「VersionPurpose 13 值」。
P9A 之前**全仓没有这个词表的代码表达** —— 只有注释和字典文档，
于是每个调用方都得自己猜（bug-180~191 的同构坑：词表不在类型里 → 客户端猜 → 猜错
→ 生产静默错）。

这里用 `Literal` 而不是新建 `Enum`：该列的 **DB 类型是 VARCHAR(40)**，把它改成
PG native enum 是一次带漂移风险的迁移，而 P9A 的写面并不需要。
`Literal` 已经给出编译期检查 + FastAPI 的 422，成本为零。
字典出处：`spec/工艺专用综合计算软件——合并数据字典.md:882`。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

#: VersionPurpose 13 值（合并数据字典逐字）。
#: 新增值要同时改字典、本常量与 `SignatureMatrix.version_purpose` 的取值。
VersionPurpose = Literal[
    "INTER_DISCIPLINE_CHECK",
    "INTERNAL_REVIEW",
    "CUSTOMER_REVIEW",
    "RE_CUSTOMER_REVIEW",
    "ISSUED_FOR_DESIGN",
    "ISSUED_FOR_PURCHASE",
    "ISSUED_FOR_CONSTRUCTION",
    "ISSUED_FOR_USE",
    "ISSUED_FOR_BID",
    "ISSUED_FOR_CHANGE",
    "AS_BUILT",
    "INFORMATION_ONLY",
    "VOID",
]


class DeliverableIssueRequest(BaseModel):
    """签发交付物版本的请求体。"""

    version_purpose: VersionPurpose = Field(
        description="13 值词表之一（合并数据字典）"
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="版本说明；留空则写默认文案",
    )


class DeliverableIssueResponse(BaseModel):
    """签发结果（P9A-DLV-010 显式声明，零裸字段）。

    字段集合被 `test_response_model_has_no_bare_fields` 钉死 ——
    加字段要同时改那个测试，这是刻意的：契约变化必须是显式动作。
    """

    deliverable_id: uuid.UUID
    version_id: uuid.UUID
    rev: str = Field(description="版本号，字符串（'1'/'2'/…）")
    doc_no: str
    version_purpose: str
    sign_status: str = Field(description="签发后为 PENDING")
    issued_at: datetime = Field(description="版本签发时刻（= 版本行 created_at）")
