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
    cfg = ProjectTemplateConfig(
        record_approval=RecordApprovalConfig(steps=[{"role": "审核", "level": 1}]),
        stream_approval=StreamApprovalConfig(max_depth=1),
        numbering=NumberingConfig(segments=[{"type": "SEQ"}], separator="-"),
        customer_approval=CustomerApprovalConfig(proxy_allowed=False),
        signature_matrix=SignatureMatrixBinding(
            matrix_name="DEFAULT_1_LEVEL", steps=[{"role": "DESIGNER"}]
        ),
        version_sequence=VersionSequenceConfig(allowed_purposes=["DRAFT"]),
        reversal_role=ReversalRoleConfig(reversal_approver_role="DESIGNER"),
    )
    assert cfg.record_approval.steps[0].role == "审核"

def test_invalid_config_raises_pcs_error():
    from app.services.exceptions import PcsError
    from app.services.project_template_service import ProjectTemplateService
    with pytest.raises(PcsError) as exc_info:
        ProjectTemplateService.validate_config({
            "stream_approval": {"max_depth": 5},  # 越界
        })
    assert exc_info.value.code == "TEMPLATE_CONFIG_INVALID"
