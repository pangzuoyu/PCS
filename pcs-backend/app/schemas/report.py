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

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.report.style import (
    HeaderFooterConfig,
    Margins,
    ReportStyle,
    TableStyle,
)

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


#: **禁止从 API 写入的样式字段**，及理由。
#:
#: 1. `font_dir` —— 服务器上的**文件系统路径**，PDF 渲染器拿它定位 TTF。
#:    开放写入等于让调用方指定渲染器去读哪个目录下的文件（目录遍历入口）。
#:    它只该来自服务端配置 `get_settings().report_font_dir`。
#: 2. `locked_fields` —— 「**哪些字段锁死**」的名单本身。放进可写字段里，
#:    用户就能传 `locked_fields: ["font_size_body"]` 给自己解锁，
#:    公司强制标准（`page_size` / `orientation`）再也锁不住。
#:    注意 `resolve()` 已有防护（合并后还原 `defaults.locked_fields`），
#:    但那防的是「通过合并解锁」；这里是防「把名单存进库里长期生效」。
STYLE_FIELDS_NOT_WRITABLE = frozenset({"font_dir", "locked_fields"})


class ReportStyleCreate(BaseModel):
    """建样式。`style` 是**局部补丁**，不是完整样式。

    ⚠️ 用 `exclude_unset` 语义：只存用户**显式设置过**的字段，
    未设置的沿用代码默认值 —— 这正是 `resolve()` 的合并前提
    （裁决：初始样式不落库，第一次改才落，且只落改动部分）。
    落库「完整样式」会引入「代码默认值升级了、库里那份还是旧的」的问题。
    """

    model_config = {"extra": "forbid"}

    report_type: str = Field(max_length=64)
    project_id: uuid.UUID | None = None
    style: "StylePatch" = Field(default_factory=dict)


class StylePatch(BaseModel):
    """样式局部补丁。

    `extra="forbid"`：拼错字段名必须报错。Pydantic 默认 `ignore` 会让
    `font_size_bodyy` 静默通过、返回 201、而样式毫无变化 ——
    「保存成功但什么都没变」是比报错更难查的故障。

    禁写字段用 `model_validator` 在**模型层**拦，而不是端点里逐个判断：
    少一个端点就少一处漏判。
    """

    model_config = {"extra": "forbid"}

    page_size: Literal["A4", "A3", "Letter"] | None = None
    orientation: Literal["portrait", "landscape"] | None = None
    margins: Margins | None = None
    font_family_cn: str | None = Field(default=None, max_length=64)
    font_family_en: str | None = Field(default=None, max_length=64)
    font_size_body: int | None = Field(default=None, ge=4, le=40)
    font_size_heading: int | None = Field(default=None, ge=4, le=60)
    line_spacing: float | None = Field(default=None, gt=0, le=5)
    header: HeaderFooterConfig | None = None
    footer: HeaderFooterConfig | None = None
    table: TableStyle | None = None
    assumption_mark: str | None = Field(default=None, max_length=8)
    assumption_color: str | None = Field(default=None, max_length=16)
    qr_position: Literal["footer", "header"] | None = None
    qr_size_mm: int | None = Field(default=None, ge=5, le=100)
    heat_exchanger_type: Literal["AIR_COOLER", "SHELL_TUBE"] | None = None

    @model_validator(mode="after")
    def _no_non_writable(self) -> "StylePatch":
        given = self.model_fields_set & STYLE_FIELDS_NOT_WRITABLE
        if given:
            raise ValueError(
                f"这些字段不允许通过 API 写入：{sorted(given)}")
        return self


class ReportStyleRevise(BaseModel):
    """改样式 = 新增一版本。只带 `style` 补丁。"""

    model_config = {"extra": "forbid"}

    style: StylePatch = Field(default_factory=dict)


ReportStyleCreate.model_rebuild()


__all__ = ["ReportGenerateRequest", "ReportGenerateResponse", "ReportFileStatusResponse",
           "ReportVerifyResponse", "ReportHashResponse", "ReportStyleSummary",
           "ReportStyleListResponse", "ReportStyleCreate", "ReportStyleRevise",
           "StylePatch", "STYLE_FIELDS_NOT_WRITABLE", "SUPPORTED_OUTPUT_FORMATS"]