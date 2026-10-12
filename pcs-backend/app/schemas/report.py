"""`/api/v1/report` 的请求/响应模型。

**零裸 object 响应**（P9A-DLV-010 硬约束）：每个字段都显式声明类型。
裸 `object` / `array` 会让 `openapi-typescript` 生成 `any`，P9B 的
「类型来自 ./api」纪律就断了 —— 前端从此退回手写 interface。

`verify` 端点的响应**刻意不含哈希**（用户 2026-10-08 裁决）：比对的主语是
**系统**（现场扫码的人手里没有原始文件，算不出哈希），给他哈希值也用不上。
要完整哈希的审计角色走 `/{id}/hash` 端点 —— **两个消费者，两个端点**。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.services.report.style import ReportStyle

# SPEC §3.2.2(2) 的 output_format 枚举；Excel/CSV 走 xlsx 渲染器
SUPPORTED_OUTPUT_FORMATS = ("pdf", "xlsx", "docx")


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(max_length=64)
    project_id: uuid.UUID
    record_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10000)
    output_format: str = Field(default="pdf", max_length=16)


class ReportGenerateResponse(BaseModel):
    """202 Accepted —— 生成是异步的（10k 行 PDF ≈ 10 CPU-秒，同步会阻塞 event loop）。"""

    task_id: str
    status: str = "PENDING"


class ReportFileStatusResponse(BaseModel):
    report_file_id: uuid.UUID
    status: str
    file_format: str
    size_bytes: int
    error_message: str | None = None
    heartbeat_at: datetime | None = None


class ReportVerifyResponse(BaseModel):
    """校验结论。**不含任何哈希**（用户 2026-10-08 裁决）。

    字段集合被 `test_verify_endpoint_returns_verdict_only` 用 `set(body) ==` 钉死，
    加字段就要同步想清楚「现场人员看到这个字段有什么用」——没有就别加。
    """

    match: bool
    doc_no: str | None = None
    rev: str | None = None
    generated_at: datetime | None = None


class ReportHashResponse(BaseModel):
    """审计角色的完整哈希。与 ReportVerifyResponse 分端点，因为消费者与敏感度都不同。"""

    report_file_id: uuid.UUID
    record_hash_digest: str
    data_version: str | None = None
    generated_at: datetime | None = None


class ReportStyleSummary(BaseModel):
    style_id: uuid.UUID
    report_type: str
    project_id: uuid.UUID | None = None
    version: str
    status: str
    style: ReportStyle


class ReportStyleListResponse(BaseModel):
    items: list[ReportStyleSummary]
    total: int


__all__ = ["ReportGenerateRequest", "ReportGenerateResponse", "ReportFileStatusResponse",
           "ReportVerifyResponse", "ReportHashResponse", "ReportStyleSummary",
           "ReportStyleListResponse", "SUPPORTED_OUTPUT_FORMATS"]