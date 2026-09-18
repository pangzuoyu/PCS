from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ApprovalStep(BaseModel):
    """单步审批定义（项目模板 record_approval.steps 内嵌项）。

    业务：role 指定审批角色（DESIGNER/CHECKER/REVIEWER/APPROVER），
    level 1-4 步；can_self_check/can_skip 控制是否允许自校/跳过（流程柔性）。
    """

    role: str = Field(
        ..., min_length=1, description="审批角色（DESIGNER/CHECKER/REVIEWER/APPROVER）"
    )
    level: int | None = Field(None, ge=1, le=4, description="审批层级（1-4 步审批）")
    required: bool = Field(True, description="是否必须审批")
    can_self_check: bool = Field(False, description="是否允许自校")
    can_skip: bool = Field(False, description="是否允许跳过")


class RecordApprovalConfig(BaseModel):
    """记录审批配置（项目模板内嵌段，1~4 步审批步骤列表）。

    业务：项目级审批流 1~4 步；min_length=1（项目必须至少有 1 步），
    max_length=4（最多 4 步，对应 SPEC §3.1 锁定）。
    """

    steps: list[ApprovalStep] = Field(
        ..., min_length=1, max_length=4, description="审批步骤 1~4 步"
    )


class StreamApprovalConfig(BaseModel):
    """物流审批深度配置（项目模板内嵌段，锁定 1/2 步）。

    业务：max_depth=1 表示仅 1 级审批（自校），max_depth=2 表示 2 级审批
    （校核 + 审核）；默认 2 是较严的项目标准。
    """

    max_depth: Literal[1, 2] = Field(2, description="物流审批最大深度 1 或 2 步")


class NumberingSegment(BaseModel):
    """编号片段定义（项目模板 numbering.segments 内嵌项）。

    业务：6 种类型片段（PREFIX/PROJECT_CODE/SEQ/SUFFIX/YEAR/CATEGORY）按序拼接
    生成项目编号；value 仅 PREFIX/SUFFIX/CATEGORY 必填（具体字面值）。
    """

    type: Literal["PREFIX", "PROJECT_CODE", "SEQ", "SUFFIX", "YEAR", "CATEGORY"] = Field(
        ..., description="编号片段类型"
    )
    value: str | None = Field(None, max_length=50, description="片段字面值（如 PREFIX='P-'）")


class NumberingConfig(BaseModel):
    """编号规则配置（项目模板内嵌段，定义位号生成器）。

    业务：segments 按序拼接生成位号（P-、项目代码-、序号-...），
    separator 片段间分隔符（默认 -），revision_separate 控制版本号是否独立。
    """

    segments: list[NumberingSegment] = Field(..., min_length=1, description="编号片段列表")
    separator: str = Field(default="-", max_length=5, description="片段间分隔符")
    revision_separate: bool = Field(True, description="版本号是否独立分隔")


class CustomerApprovalConfig(BaseModel):
    """业主审批配置（项目模板内嵌段，控制业主侧签批规则）。

    业务：proxy_allowed 控制业主是否允许代理签批，
    attachment_required 默认 True 要求业主审批带附件（合规归档）。
    """

    proxy_allowed: bool = Field(False, description="是否允许代理签批")
    attachment_required: bool = Field(True, description="是否必须附件")


class SignatureMatrixBinding(BaseModel):
    """签署矩阵绑定（项目模板内嵌段，引用公司级签名矩阵）。

    业务：matrix_name 引用签名矩阵名（如 DESIGN_MATRIX），steps 是 1~4 步
    审批步骤；与 record_approval 互斥（用其一即可）。
    """

    matrix_name: str = Field(..., min_length=1, max_length=100, description="签署矩阵名")
    steps: list[ApprovalStep] = Field(..., min_length=1, description="签署步骤")


class VersionSequenceConfig(BaseModel):
    """版本序列配置（项目模板内嵌段，控制 A/B/C 版本号生成）。

    业务：skip_alpha_versions 控制是否跳过 A/B/C 字母版本（默认 False）；
    allowed_purposes 限定允许的版本用途（DRAFT/PUBLISHED/CHANGE_NOTICE）。
    """

    skip_alpha_versions: bool = Field(False, description="是否跳过 A/B/C 字母版本")
    allowed_purposes: list[Literal["DRAFT", "PUBLISHED", "CHANGE_NOTICE"]] = Field(
        default_factory=lambda: ["DRAFT", "PUBLISHED"],
        description="允许的版本用途",
    )


class ReversalRoleConfig(BaseModel):
    """逆审角色配置（项目模板内嵌段，指定可执行 REVERSAL_PENDING 审批的角色）。

    业务：reversal_approver_role 指定哪个角色（DESIGNER/APPROVER）有权批准
    记录状态从 CHANGED 撤回到 DRAFT；一般限定为高权限角色（不可自逆）。
    """

    reversal_approver_role: str = Field(..., min_length=1, description="可逆审批角色")


class ProjectTemplateConfig(BaseModel):
    """项目模板配置根（项目级模板总入口，承载 7 段可配置子项）。

    业务：7 段均为 Optional（项目模板按需配置），分别覆盖：
    记录审批/物流审批/编号规则/业主审批/签署矩阵/版本序列/逆审角色。
    """

    record_approval: RecordApprovalConfig | None = Field(None, description="记录审批配置")
    stream_approval: StreamApprovalConfig | None = Field(None, description="物流审批配置")
    numbering: NumberingConfig | None = Field(None, description="编号规则配置")
    customer_approval: CustomerApprovalConfig | None = Field(None, description="业主审批配置")
    signature_matrix: SignatureMatrixBinding | None = Field(None, description="签署矩阵绑定")
    version_sequence: VersionSequenceConfig | None = Field(None, description="版本序列配置")
    reversal_role: ReversalRoleConfig | None = Field(None, description="逆审角色配置")