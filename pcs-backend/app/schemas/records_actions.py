"""records 写端点的请求/响应 schema（P9A B4）。

`records.py` 既有 6 个端点全是 `response_model=dict`（TODO-039/041 的既有债，
**本轮不动**）。本文件是新端点的契约面，与 `app/schemas/records.py` 分开 ——
同一个模块里混着「零裸字段的新契约」和「裸 dict 的旧债」，读者会以为前者也不保证。

P9A-DLV-010：每个响应模型**显式声明**，禁止 `dict` / `object`。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecordActionResponse(BaseModel):
    """记录写动作的统一结果。

    四个字段对三个端点够用：`record_type` 让前端不必回查就知道操作了哪类记录，
    `from_status` / `to_status` 让「为什么状态变了」在响应里自证。
    """

    record_type: str = Field(description="RECORD_TYPE_REGISTRY 的键，如 PipingResult")
    record_id: uuid.UUID
    from_status: str = Field(description="动作前的 sign_status")
    to_status: str = Field(description="动作后的 sign_status")


class ObsoleteRequest(BaseModel):
    """弃用记录（ADR-0009）。理由必填 —— 空理由的弃用事后无从追溯为什么作废。"""

    reason: str = Field(min_length=1, max_length=200)


class RequestReversalRequest(BaseModel):
    """发起撤销申请（ADR-0002）。理由必填，同上。"""

    reason: str = Field(min_length=1, max_length=500)


#: 撤销裁决 2 值。APPROVE 与 REJECT 是**相反动作**，两个分支都要能走通 ——
#: 只接通 approve 的半成品会让「拒绝撤销」永远 500，记录卡在 REVERSAL_PENDING。
ReversalDecision = Literal["APPROVE", "REJECT"]


class ReversalDecisionRequest(BaseModel):
    """撤销裁决（ADR-0010：3 级 REVIEWER / 4 级 APPROVER）。"""

    decision: ReversalDecision
    reason: str = Field(default="", max_length=500)


#: ApprovalRole 7 值，逐字取自 `app/models/project.py:154` 的列注释。
#: 该词表此前只存在于注释里 —— 与 P9A 交付物的 VersionPurpose 同一个形状
#: （词表不在类型里 → 调用方猜 → 猜错静默）。
ApprovalRole = Literal[
    "DESIGNER",
    "CHECKER",
    "REVIEWER",
    "APPROVER",
    "SYSTEM_ADMIN",
    "PROCESS_CONTROLLER",
    "DATA_ADMIN",
]


class SubmitApprovalRequest(BaseModel):
    """提交送审（DRAFT / CHECK_REJECTED → IN_APPROVAL）。

    `approval_role` 由提交人指定：本仓**没有**批准角色链的定义来源
    （`project_templates.default_config_json` 的 `record_approval_config`
    只有一句注释、无消费方），所以待批角色是显式输入而不是推导出来的。
    服务端只做两件事：校验它在 7 值词表内、且**不等于提交人自己的角色**。
    """

    approval_role: ApprovalRole
    approval_depth: int = Field(default=1, ge=1, le=4)


class SubmitApprovalResponse(BaseModel):
    """提交结果。"""

    model_config = ConfigDict(from_attributes=True)

    record_type: str
    record_id: uuid.UUID
    from_status: str
    to_status: str
    approval_step: int
    approval_depth: int
    approval_role: str


#: 批准裁决 2 值。PASS 与 REJECT 相反，两个分支都要能走通。
ApprovalDecision = Literal["PASS", "REJECT"]


class ApprovalStepRequest(BaseModel):
    """推进/退回当前批准步骤。"""

    decision: ApprovalDecision
    reason: str = Field(default="", max_length=500)


class ApprovalStepResponse(BaseModel):
    """推进结果。`approval_step` / `approval_depth` 是「Step n/N」进度条的数据源。"""

    record_type: str
    record_id: uuid.UUID
    from_status: str
    to_status: str
    approval_step: int
    approval_depth: int


class CommentCreateRequest(BaseModel):
    """新增批注。

    `body` 额外拒纯空白（`"   "`）：`min_length=1` 拦不住它，
    而一屏空行等于这一屏没内容 —— 却会让人以为「有人回过」。

    用 `field_validator` 而不是正则约束：Pydantic 的 Rust regex **不支持
    look-ahead**（`^(?!\s*$).+` 会直接 SchemaError），正着写又拦不住尾部空白。
    """

    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("批注内容不能为空白")
        return stripped


class CommentResponse(BaseModel):
    """单条批注。字段集合被 `test_comment_response_has_no_bare_fields` 钉死。"""

    model_config = ConfigDict(from_attributes=True)

    comment_id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    body: str
    author_id: uuid.UUID
    created_at: datetime


class CommentListResponse(BaseModel):
    """批注列表 + 总数（总数单独查而不复用 len(items) —— 列表有 limit）。"""

    items: list[CommentResponse]
    total: int
