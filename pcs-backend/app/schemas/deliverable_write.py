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
from datetime import date, datetime
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


#: 签署决策 3 值。`SIGN` 与 `RETURN` 是**相反动作**，`SKIP` 只在矩阵
#: `can_skip=true` 时允许 —— 三者都要能走通，只接通 SIGN 的半成品会让
#: 「退回」永远 500，而退回是签署流程里唯一能纠错的路径。
SignDecision = Literal["SIGN", "RETURN", "SKIP"]


class SignStepRequest(BaseModel):
    """推进签署矩阵某一步的请求体。"""

    version_id: uuid.UUID = Field(description="被签的版本行")
    step_index: int = Field(ge=1, description="步骤序号，1 起")
    decision: SignDecision = Field(description="SIGN / RETURN / SKIP")


class SignStepResponse(BaseModel):
    """推进结果。字段集合被 `test_response_model_has_no_bare_fields` 钉死。"""

    deliverable_id: uuid.UUID
    version_id: uuid.UUID
    step_index: int
    step_role: str = Field(description="矩阵 steps_json.sign_role")
    decision: SignDecision
    state: str = Field(description="COMPLETED / FAILED / SKIPPED")
    deliverable_sign_status: str = Field(
        description="推进后交付物的签署状态（DRAFT/PENDING/APPROVED）"
    )
    signed_at: datetime = Field(description="本步动作发生时刻")


#: 客户批准方式 4 值（ADR-0007：客户在系统外以这四种方式之一批准）。
CustomerApprovalMethod = Literal["EMAIL", "LETTER", "EDMS", "SIGNED_DOC"]

#: 凭证附件类型 4 值（ADR-0007 + P9A-DLV-008）。
CredentialFileType = Literal["PDF", "JPG", "PNG", "EML"]


class CustomerApprovalProxyRequest(BaseModel):
    """代录客户批准（P9A B3 / ADR-0007）。

    ⚠️ **刻意不收 `file_hash`** —— 收了就等于让客户端自证物证，
    而物证是客户批准唯一的存在性证明。哈希由服务端从磁盘上的真实文件算。
    ⚠️ `secondary_password` 出现在请求体里是路径 B 的固有形状（MFA 决议 §3），
    它**绝不**进审计与日志（见 `secondary_auth` 模块）。
    """

    version_id: uuid.UUID = Field(description="客户批准针对的版本行")
    file_path: str = Field(description="凭证相对存储根的路径；服务端据此读盘算哈希")
    file_name: str = Field(max_length=200)
    file_type: CredentialFileType
    approver_name: str = Field(max_length=100, description="客户方批准人姓名")
    approval_date: date = Field(description="客户批准日期")
    approval_method: CustomerApprovalMethod
    secondary_username: str = Field(max_length=100, description="代录人 AD 用户名")
    secondary_password: str = Field(max_length=200)


class CustomerApprovalProxyResponse(BaseModel):
    """代录结果。字段集合被 `test_response_model_has_no_bare_fields` 钉死。"""

    deliverable_id: uuid.UUID
    version_id: uuid.UUID
    attachment_id: uuid.UUID
    customer_approver_name: str
    approval_date: date
    approval_method: CustomerApprovalMethod
    is_proxy: bool = Field(description="恒为 True —— 本端点就是代录入口")
    proxied_at: datetime = Field(description="代录时刻")
