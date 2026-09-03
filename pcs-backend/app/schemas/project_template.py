from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ApprovalStep(BaseModel):
    role: str = Field(..., min_length=1)
    level: int | None = None
    required: bool = True
    can_self_check: bool = False
    can_skip: bool = False

class RecordApprovalConfig(BaseModel):
    steps: list[ApprovalStep] = Field(..., min_length=1, max_length=4)

class StreamApprovalConfig(BaseModel):
    max_depth: Literal[1, 2] = 2

class NumberingSegment(BaseModel):
    type: Literal["PREFIX", "PROJECT_CODE", "SEQ", "SUFFIX", "YEAR", "CATEGORY"]
    value: str | None = None

class NumberingConfig(BaseModel):
    segments: list[NumberingSegment] = Field(..., min_length=1)
    separator: str = Field(default="-", max_length=5)
    revision_separate: bool = True

class CustomerApprovalConfig(BaseModel):
    proxy_allowed: bool = False
    attachment_required: bool = True

class SignatureMatrixBinding(BaseModel):
    matrix_name: str
    steps: list[ApprovalStep] = Field(..., min_length=1)

class VersionSequenceConfig(BaseModel):
    skip_alpha_versions: bool = False
    allowed_purposes: list[Literal["DRAFT", "PUBLISHED", "CHANGE_NOTICE"]] = Field(
        default_factory=lambda: ["DRAFT", "PUBLISHED"]
    )

class ReversalRoleConfig(BaseModel):
    reversal_approver_role: str

class ProjectTemplateConfig(BaseModel):
    record_approval: RecordApprovalConfig | None = None
    stream_approval: StreamApprovalConfig | None = None
    numbering: NumberingConfig | None = None
    customer_approval: CustomerApprovalConfig | None = None
    signature_matrix: SignatureMatrixBinding | None = None
    version_sequence: VersionSequenceConfig | None = None
    reversal_role: ReversalRoleConfig | None = None
