"""交付物 API schema（P1-7+ D 模块 / P8 前置）。

P1 spec §3.2 定义 5 个端点：create / issue / versions / snapshot / customer-approval-proxy。
变更单不是独立实体，而是 `deliverable_type=CHANGE_NOTICE` 的交付物，
由 `change_notice_details` 1:1 扩展承载 change_type/reason（spec 第 215 行）。

本文件只覆盖**读面**（list / versions / snapshot）—— P8 REPORT 的实际依赖是
「从 deliverables / deliverable_versions 读数据」。三个写端点（create / issue /
proxy）服务的是 P9 签署流程，尚未落地，见 TODOS.md 的 P8 前置项 ②。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeliverableResponse(BaseModel):
    """交付物列表项 / 详情。

    只暴露报表与签署流程要用的字段；`record_snapshot_json` 等大 JSONB 不进列表响应，
    走 snapshot 端点按需取（spec §3.2 的 snapshot 端点正是为此存在）。
    """

    model_config = ConfigDict(from_attributes=True)

    deliverable_id: uuid.UUID
    project_id: uuid.UUID
    deliverable_type: str = Field(description="CALCULATION_BOOK/DRAWING/CHANGE_NOTICE 等")
    scope_type: str
    scope_value: str | None = None
    doc_no: str
    doc_no_mode: str
    title: str
    current_rev: str = Field(description="当前 Rev：A/B/0/1/AS-BUILT/X")
    current_version_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "当前 Rev 对应的版本行 id（`rev == current_rev` 的那条）。"
            "没有版本行 / 没有同 Rev 的版本 ⇒ null。"
            "⚠️ Rev 是自由文本，前端不能靠猜 —— 签署工作流的 workflow_id 要的是版本 id"
        ),
    )
    version_purpose: str
    sign_status: str
    matrix_id: uuid.UUID | None = None
    parent_deliverable_id: uuid.UUID | None = None
    customer_approval_date: date | None = None
    customer_approver_name: str | None = None
    created_at: datetime | None = None


class DeliverableListResponse(BaseModel):
    """项目下的交付物列表。

    `total` 供前端分页；P8 REPORT 生成页要按 deliverable_type 分组展示。
    """

    items: list[DeliverableResponse]
    total: int


class DeliverableVersionResponse(BaseModel):
    """单个 Rev 的历史条目（spec §3.2 的 versions 端点）。

    `record_snapshot_json` 是「记录ID+哈希汇总」，可能很大 —— 故默认不进响应，
    由 snapshot 端点按 rev 取。`pdf_file_path` 同理不进响应（是文件路径不是内容）。
    """

    model_config = ConfigDict(from_attributes=True)

    version_id: uuid.UUID
    deliverable_id: uuid.UUID
    rev: str
    version_purpose: str
    description: str
    affected_status: str | None = None
    customer_approval_date: date | None = None
    created_at: datetime | None = None


class RecordBindingResponse(BaseModel):
    """snapshot 端点里的单条记录绑定明细。

    报表要回答「这份 Rev 锁定了哪些记录、各自哈希是多少」——
    `old_record_hash_before_change` 用于识别「相对上一版哪些记录实质变了」。
    """

    model_config = ConfigDict(from_attributes=True)

    record_type: str
    record_id: uuid.UUID
    record_hash: str
    old_record_hash_before_change: str | None = None


class DeliverableSnapshotResponse(BaseModel):
    """某 Rev 的完整快照：Rev 元信息 + 记录绑定明细 + 签署汇总。

    P8 REPORT 的二维码溯源依赖 `record_hash` 链；`signature_summary_json` 原样
    透传（其结构由签署矩阵定义，本层不解释，避免两层耦合）。
    """

    deliverable_id: uuid.UUID
    rev: str
    version_purpose: str
    description: str
    doc_no: str
    sign_status: str
    record_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    signature_summary_json: dict[str, Any] = Field(default_factory=dict)
    bindings: list[RecordBindingResponse]

class DeliverableActionRow(BaseModel):
    """内部行模型：审计记录 → 动作条目（`detail_json` 仍是 dict）。

    对外暴露的是 `schemas/deliverable_actions.DeliverableActionResponse`，
    那里 `detail_json` 已是 JSON 文本 —— 本模型只在 service 层内部流转。
    """

    model_config = ConfigDict(from_attributes=True)

    action: str
    resource_type: str
    resource_id: str
    actor_user_id: uuid.UUID | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime | None = None


class TodoResponse(BaseModel):
    """一条待办（实时计算的结果，不落库）。字段集合被契约测试钉死。"""

    deliverable_id: uuid.UUID
    version_id: uuid.UUID
    project_id: uuid.UUID = Field(description="越权过滤在 service 层按此列完成")
    step_order: int
    step_role: str = Field(description="当前该签这一步要求的角色")
    title: str


class TodoListResponse(BaseModel):
    """待办列表。`total` = `len(items)` —— 没有分页，因为没有可分页的表。"""

    items: list[TodoResponse]
    total: int
