"""records 写端点的请求/响应 schema（P9A B4）。

`records.py` 既有 6 个端点全是 `response_model=dict`（TODO-039/041 的既有债，
**本轮不动**）。本文件是新端点的契约面，与 `app/schemas/records.py` 分开 ——
同一个模块里混着「零裸字段的新契约」和「裸 dict 的旧债」，读者会以为前者也不保证。

P9A-DLV-010：每个响应模型**显式声明**，禁止 `dict` / `object`。
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


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
