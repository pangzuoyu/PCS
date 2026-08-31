"""V3.1 Schema 层契约：表数量、关键约束、ADR-0023 复合键。"""

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


@pytest.fixture(scope="module")
def inspector():
    eng = create_engine(get_settings().database_url)
    insp = inspect(eng)
    yield insp
    eng.dispose()


def test_table_count_is_53(inspector):
    tables = inspector.get_table_names()
    assert "alembic_version" in tables
    assert len(tables) == 54, f"expected 54 incl. alembic_version, got {len(tables)}"


def test_required_tables_present(inspector):
    required = {
        "projects",
        "workspaces",
        "users",
        "streams",
        "stream_state_points",
        "config_assets",
        "config_versions",
        "config_approvals",
        "formula_definitions",
        "coefficient_tables",
        "template_files",
        "project_templates",
        "pipe_classes",
        "project_pipe_classes",
        "numbering_templates",
        "doc_no_sequences",
        "flash_results",
        "piping_results",
        "pipe_network_results",
        "pump_results",
        "psv_results",
        "flare_system_results",
        "vessel_results",
        "sep_equip_results",
        "heat_results",
        "cv_results",
        "restriction_results",
        "cooling_tower_results",
        "psychro_results",
        "open_channel_results",
        "filtration_results",
        "cost_est_results",
        "equipment_list",
        "equipment_type_codes",
        "equipment_lib",
        "suppliers",
        "deliverables",
        "deliverable_versions",
        "deliverable_record_bindings",
        "signature_matrices",
        "project_signature_matrix_bindings",
        "customer_approval_attachments",
        "change_notice_details",
        "record_change_snapshots",
        "data_lineage",
        "project_input_checklist",
        "audit_logs",
        "system_settings",
        "report_definitions",
        "report_execution_logs",
        "document_chunks",
        "ai_audit_log",
        "license_configs",
    }
    present = set(inspector.get_table_names())
    missing = required - present
    assert not missing, f"missing tables: {missing}"


def test_equipment_type_codes_composite_pk(inspector):
    """ADR-0023: equipment_type_codes 必须有复合 PK (project_id, type_code)。"""
    pk = inspector.get_pk_constraint("equipment_type_codes")
    assert sorted(pk["constrained_columns"]) == ["project_id", "type_code"], pk


def test_equipment_list_composite_fk_to_equipment_type_codes(inspector):
    """ADR-0023: equipment_list 复合 FK → equipment_type_codes。"""
    fks = inspector.get_foreign_keys("equipment_list")
    target = [f for f in fks if f["referred_table"] == "equipment_type_codes"]
    assert len(target) == 1, f"expected 1 FK, got {len(target)}"
    fk = target[0]
    assert sorted(fk["constrained_columns"]) == ["equipment_type_project_id", "type_code"]
    assert sorted(fk["referred_columns"]) == ["project_id", "type_code"]


def test_record_mixin_columns_present(inspector):
    """RecordMixin 字段全部出现在计算结果表（含 sign_status 9 态枚举）。"""
    cols = {c["name"] for c in inspector.get_columns("pump_results")}
    must_have = {
        "sign_status",
        "record_hash",
        "approval_step",
        "approval_depth",
        "approval_role",
        "locked_by_deliverable",
        "change_pending_since",
        "obsoleted_reason",
        "reversal_requested_at",
    }
    missing = must_have - cols
    assert not missing, f"missing mixin cols in pump_results: {missing}"


def test_recordsignstatus_enum_has_9_values(inspector):
    """SUP-007 §3.1: 9 态枚举。"""
    eng = create_engine(get_settings().database_url)
    with eng.connect() as c:
        rows = c.execute(
            text("SELECT unnest(enum_range(NULL::recordsignstatus))::text")
        ).fetchall()
    eng.dispose()
    vals = {r[0] for r in rows}
    expected = {
        "DRAFT",
        "IN_APPROVAL",
        "CHECKED",
        "CHECK_REJECTED",
        "STALE",
        "CHANGE_PENDING",
        "CHANGED",
        "REVERSAL_PENDING",
        "OBSOLETE",
    }
    missing = expected - vals
    assert not missing, f"missing enum values: {missing} (got {sorted(vals)})"
