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


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(get_settings().database_url)
    yield eng
    eng.dispose()


def test_table_count(inspector):
    tables = inspector.get_table_names()
    assert "alembic_version" in tables
    # 53（V3.1 基线）+ pcs_toe_conversion_factors + htri_template_schemas
    # + pipe_class_import_previews（SUP-002 PC-5）+ alembic_version = 57
    # SUP-002 SYM-1 新增 stream_symbols + project_stream_symbols = 59
    # SUP-002 FMT-1+FMT-3 新增 pipe_code_templates + project_pipe_code_configs
    #   + project_pipe_code_sequences = 62
    # SUP-002 INT-1 新增 project_template_pipe_classes = 63
    # P3.x SIM-14 新增 sim_imports + sim_import_warnings = 65
    assert len(tables) == 65, f"expected 65 incl. alembic_version, got {len(tables)}"


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
        "stream_symbols",
        "project_stream_symbols",
        "pipe_code_templates",
        "project_pipe_code_configs",
        "project_pipe_code_sequences",
    }
    present = set(inspector.get_table_names())
    missing = required - present
    assert not missing, f"missing tables: {missing}"


def test_equipment_type_codes_composite_unique(inspector):
    """Sprint 3: PK → UNIQUE（允许 project_id NULL）。约束列必须是 (project_id, type_code)。"""
    uqs = inspector.get_unique_constraints("equipment_type_codes")
    target = [u for u in uqs if sorted(u["column_names"]) == ["project_id", "type_code"]]
    assert len(target) == 1, f"expected 1 UNIQUE on (project_id, type_code), got {uqs}"


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


def test_fk_violation_raises(engine):
    """端到端验证：FK 约束被强制执行（非仅声明）。
    插入带不存在 project_id 的 stream 应被 DB 拒绝（IntegrityError）。
    防止 ADR-0023 复合 FK 声明丢失但实际不生效的回归。
    """
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO streams "
                    "(stream_id, project_id, workspace_id, stream_name, data_mode) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), "
                    "gen_random_uuid(), 'FK_TEST', 'CHEMICAL')"
                )
            )
