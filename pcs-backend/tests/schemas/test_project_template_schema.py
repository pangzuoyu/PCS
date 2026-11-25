"""项目模板 Pydantic schema 验证测试（app/schemas/project_template.py）。

覆盖 8 个 config 子 schema + ProjectTemplateConfig 完整加载 +
ProjectTemplateService.validate_config 抛 PcsError(TEMPLATE_CONFIG_INVALID)。
"""
import pytest
from pydantic import ValidationError

from app.schemas.project_template import (
    CustomerApprovalConfig,
    NumberingConfig,
    ProjectTemplateConfig,
    RecordApprovalConfig,
    ReversalRoleConfig,
    SignatureMatrixBinding,
    StreamApprovalConfig,
    VersionSequenceConfig,
)


def test_record_approval_config_valid():
    cfg = RecordApprovalConfig(steps=[{"role": "审核", "level": 1}, {"role": "审定", "level": 2}])
    assert cfg.steps[1].level == 2

def test_stream_approval_config_levels_1_to_2():
    cfg = StreamApprovalConfig(max_depth=2)
    assert cfg.max_depth == 2
    with pytest.raises(ValidationError):
        StreamApprovalConfig(max_depth=3)  # 越界

def test_numbering_config_segments():
    cfg = NumberingConfig(
        segments=[{"type": "PREFIX", "value": "PRJ"}, {"type": "SEQ"}], separator="-"
    )
    assert len(cfg.segments) == 2

def test_customer_approval_config_attachment_required():
    cfg = CustomerApprovalConfig(proxy_allowed=True, attachment_required=True)
    assert cfg.proxy_allowed

def test_signature_matrix_binding_steps():
    cfg = SignatureMatrixBinding(
        matrix_name="DEFAULT_2_LEVEL", steps=[{"role": "DESIGNER"}, {"role": "REVIEWER"}]
    )
    assert cfg.steps[1].role == "REVIEWER"

def test_version_sequence_config_skip_alpha():
    cfg = VersionSequenceConfig(skip_alpha_versions=True, allowed_purposes=["DRAFT", "PUBLISHED"])
    assert cfg.skip_alpha_versions

def test_reversal_role_config():
    cfg = ReversalRoleConfig(reversal_approver_role="REVIEWER")
    assert cfg.reversal_approver_role == "REVIEWER"

def test_full_project_template_config_loads():
    """⚠️ **7 段不能一次填满** —— `record_approval` ↔ `signature_matrix` **互斥**
    （`SignatureMatrixBinding` 的 docstring：「用其一即可」）⇒ ⇒ ⇒ 两个都填 ⇒ ⇒ ⇒
    「该谁签」有**两个答案** ⇒ ⇒ ⇒ ⇒ 所以**拆成两条**验（集合层面全覆盖）。

    ⚠️ 原先这条用例**两个都填** ⇒ ⇒ ⇒ 它证明的其实是一份**非法**配置能加载
    ⇒ ⇒ ⇒ ⇒ 现在它证明「**合法的两半**都能加载」。
    """
    common = dict(
        stream_approval=StreamApprovalConfig(max_depth=1),
        numbering=NumberingConfig(segments=[{"type": "SEQ"}], separator="-"),
        customer_approval=CustomerApprovalConfig(proxy_allowed=False),
        version_sequence=VersionSequenceConfig(allowed_purposes=["DRAFT"]),
        reversal_role=ReversalRoleConfig(reversal_approver_role="DESIGNER"),
    )
    cfg_a = ProjectTemplateConfig(
        record_approval=RecordApprovalConfig(steps=[{"role": "审核", "level": 1}]),
        **common,
    )
    cfg_b = ProjectTemplateConfig(
        signature_matrix=SignatureMatrixBinding(
            matrix_name="DEFAULT_1_LEVEL", steps=[{"role": "DESIGNER"}]
        ),
        **common,
    )
    assert cfg_a.record_approval.steps[0].role == "审核"
    assert cfg_b.signature_matrix.matrix_name == "DEFAULT_1_LEVEL"


def test_record_approval_and_signature_matrix_are_mutually_exclusive():
    """⚠️ **两个都填 ⇒ ⇒ ⇒ 拒绝**（P10-K · W-3b · C-4）。

    ⇒ ⇒ ⇒ 拒绝点在**模型**上（不是端点里手写 if）⇒ ⇒ ⇒ 任何入口都过不了。
    """
    from app.services.exceptions import PcsError
    from app.services.project_template_service import ProjectTemplateService

    with pytest.raises(PcsError) as exc_info:
        ProjectTemplateService.validate_config({
            "record_approval": {"steps": [{"role": "审核", "level": 1}]},
            "signature_matrix": {
                "matrix_name": "DEFAULT_1_LEVEL",
                "steps": [{"role": "DESIGNER"}],
            },
        })
    assert exc_info.value.code == "TEMPLATE_CONFIG_INVALID"
    assert exc_info.value.status == 422

def test_invalid_config_raises_pcs_error():
    from app.services.exceptions import PcsError
    from app.services.project_template_service import ProjectTemplateService
    with pytest.raises(PcsError) as exc_info:
        ProjectTemplateService.validate_config({
            "stream_approval": {"max_depth": 5},  # 越界
        })
    assert exc_info.value.code == "TEMPLATE_CONFIG_INVALID"
