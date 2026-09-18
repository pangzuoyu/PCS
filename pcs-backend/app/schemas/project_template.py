from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ApprovalStep(BaseModel):
    role: str = Field(
        ..., min_length=1, description="审批角色（DESIGNER/CHECKER/REVIEWER/APPROVER）"
    )
    level: int | None = Field(None, ge=1, le=4, description="审批层级（1-4 步审批）")
    required: bool = Field(True, description="是否必须审批")
    can_self_check: bool = Field(False, description="是否允许自校")
    can_skip: bool = Field(False, description="是否允许跳过")


class RecordApprovalConfig(BaseModel):
    steps: list[ApprovalStep] = Field(
        ..., min_length=1, max_length=4, description="审批步骤 1~4 步"
    )


class StreamApprovalConfig(BaseModel):
    max_depth: Literal[1, 2] = Field(2, description="物流审批最大深度 1 或 2 步")


class NumberingSegment(BaseModel):
    type: Literal["PREFIX", "PROJECT_CODE", "SEQ", "SUFFIX", "YEAR", "CATEGORY"] = Field(
        ..., description="编号片段类型"
    )
    value: str | None = Field(None, max_length=50, description="片段字面值（如 PREFIX='P-'）")


class NumberingConfig(BaseModel):
    segments: list[NumberingSegment] = Field(..., min_length=1, description="编号片段列表")
    separator: str = Field(default="-", max_length=5, description="片段间分隔符")
    revision_separate: bool = Field(True, description="版本号是否独立分隔")


class CustomerApprovalConfig(BaseModel):
    proxy_allowed: bool = Field(False, description="是否允许代理签批")
    attachment_required: bool = Field(True, description="是否必须附件")


class SignatureMatrixBinding(BaseModel):
    matrix_name: str = Field(..., min_length=1, max_length=100, description="签署矩阵名")
    steps: list[ApprovalStep] = Field(..., min_length=1, description="签署步骤")


class VersionSequenceConfig(BaseModel):
    skip_alpha_versions: bool = Field(False, description="是否跳过 A/B/C 字母版本")
    allowed_purposes: list[Literal["DRAFT", "PUBLISHED", "CHANGE_NOTICE"]] = Field(
        default_factory=lambda: ["DRAFT", "PUBLISHED"],
        description="允许的版本用途",
    )


class ReversalRoleConfig(BaseModel):
    reversal_approver_role: str = Field(..., min_length=1, description="可逆审批角色")


class ProjectTemplateConfig(BaseModel):
    record_approval: RecordApprovalConfig | None = Field(None, description="记录审批配置")
    stream_approval: StreamApprovalConfig | None = Field(None, description="物流审批配置")
    numbering: NumberingConfig | None = Field(None, description="编号规则配置")
    customer_approval: CustomerApprovalConfig | None = Field(None, description="业主审批配置")
    signature_matrix: SignatureMatrixBinding | None = Field(None, description="签署矩阵绑定")
    version_sequence: VersionSequenceConfig | None = Field(None, description="版本序列配置")
    reversal_role: ReversalRoleConfig | None = Field(None, description="逆审角色配置")