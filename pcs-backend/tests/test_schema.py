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
    # P3.x SIM-16 新增 sim_tower_results = 66
    # P3.x SIM-15 新增 sim_unit_op_results + 6 专用表 = 73
    # P4-0-2 新增 two_phase_results = 74
    # P5-OPEN-005 新增 relief_results + column_sizing + mixer_results = 77
    # P5-0-5 Task 24 新增 project_calculation_standard_profiles = 78
    # P6-1 Task 7 新增 cv_results + restriction_results = 80（注：v3.1 schema
    #   migration 提前含 cv_results / restriction_results stub，alembic chain
    #   p6_1_001 仅做 alter；实际净增 +2 列别名）
    # P6-2 Task 18 新增 flare_system_results + cooling_tower_results +
    #   psychro_results = 81（v3.1 schema 已 stub，p6_2_001 alter 净增字段）
    # P6-3 Task 29 新增 cooling_tower_curves + filtration_media_library +
    #   flare_radiation_limits = 81（v3.1 schema 已 stub 0 张）
    # P6-3 Task 30 新增 p6_3_002 仅追加列（不动表数）= 82（v3.1 schema 已 stub
    #   open_channel_results / filtration_results / cost_est_results；Task 30
    #   仅 ADD COLUMN IF NOT EXISTS 补齐派生字段）。
    # P6-4 T1 新增 p6_4_001 compound_heating_values CONFIG 表 = 83 + alembic_version
    #   = 84 incl. alembic_version。
    # P6-5 C5 新增 4 张 CONFIG 表（compound_pasquill_sigma /
    #   compound_api521_thresholds / compound_iso9613_atmospheric_absorption /
    #   compound_hammerschmidt_K）= 87 + alembic_version = 88 incl. alembic_version。
    # P6-6B 净新增 5 张 CONFIG 表（p6_6b_003 pipe_e_modulus /
    #   p6_6b_009 glycol_dehydration_full_system / p6_6b_012
    #   compound_delta_h_vap_natural_gas / p6_6b_013 drain_orifice_Cd_Y_cr，
    #   其余 p6_6b_001/004/005/006/007 均为 ALTER 不增表数）= 91 + alembic_version
    #   = 92 incl. alembic_version。
    #   P6-9-PICKUP-3 T1 删除 compound_nielsen_1988_params（P6-6B T8 表）= 91 +
    #   alembic_version = 92 incl. alembic_version。
    #   测试断言 92（含 alembic_version）= 实际 PCS 后端 schema 终态
    #   （P6-9-PICKUP-3 2026-11-15 同步）。
    # 2026-10-05: pcs 开发库从 p6_6b_013 迁到 p7_s3_004（此前落后 8 个
    # migration, 导致 test_pipe_class_migration 失败 + config_energy_conversion
    # _factors 缺 4 个 R1 分类列而 0 行）。补齐 8 张表 = 101:
    #   p7_open_009_001 utility_power_items
    #   p7_open_009_002 utility_fuel_gas
    #   p7_open_009_003 utility_heat_exchange
    #   p7_open_009_005 utility_energy_summary
    #   p7_open_009_t0 config_energy_conversion_factors
    #   p7_open_010    user_projects
    #   p7_s1_005      util_results
    #   p7_s2_001      equipment_deletion_audit
    # 2026-10-05 P7-6B 收尾: 新增 utility_gas_media (Nm³ 工艺气体/氮气/仪表空气)
    #   + utility_low_temp_heat (GJ 低温余热) = 103
    # 2026-10-05 Sprint 4 S4-0: 新增 event_idempotency (事件幂等凭据) = 104
    # 2026-10-06 p7_s5_001: 删除 equipment_lib 死表 (设备库实际由
    #   ConfigAsset CATEGORY_6 承载; 该表 0 行 / 0 引用 / 0 专属测试,
    #   SPEC P2 §3.2.6 从未要求独立表) = 103
    assert len(tables) == 103, f"expected 103 incl. alembic_version, got {len(tables)}"
    # P5-0-1b T1 新增 thermosiphon_circulation_results（SUP-010 §3.5 热虹吸循环
    #   安装高度）= 93 incl. alembic_version。
    #   （2026-10-05 起该值改为 101, 见下方 8 张表的说明。）


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
        "sim_imports",
        "sim_import_warnings",
        "sim_tower_results",
        "sim_unit_op_results",
        "sim_reactor_results",
        "sim_cstr_results",
        "sim_compressor_results",
        "sim_splitter_results",
        "sim_stca_results",
        "sim_calculator_results",
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


# ---------------------------------------------------------------------------
# OpenAPI 响应契约（2026-10-08，TODO-041 重定范围时补）
#
# 背景：pcs-frontend 的类型靠 `openapi-typescript` 从 app.openapi() 生成
# （src/types/api.d.ts）。**端点不声明 response_model，OpenAPI 里就没有该
# 路径的响应 schema，前端也就生成不出对应类型。**
#
# 行为测试抓不到这件事 —— generate 照样返回 {"code": ...}，端到端照样绿，
# 只有前端接真实 client 时才发现没有类型可用。故单列契约测试。
# ---------------------------------------------------------------------------


def _response_schema_name(paths, path, method):
    """取某个操作声明的响应 schema 名；没声明返回 None。

    ⚠️ 只看 2xx 全部码，不只看 200 —— 本项目多数写端点返回 201，
    只查 responses["200"] 会把它们全判成「无 schema」（这个错我犯过一次）。
    """
    for code, resp in paths[path][method].get("responses", {}).items():
        if not str(code).startswith("2"):
            continue
        schema = (
            resp.get("content", {}).get("application/json", {}).get("schema", {})
        )
        ref = schema.get("$ref")
        if ref:
            return ref.rsplit("/", 1)[-1]
    return None


@pytest.mark.parametrize(
    ("path", "method", "expected"),
    [
        ("/api/v1/pipe-codes/generate", "post", "GenerateResponse"),
        ("/api/v1/pipe-codes/validate", "post", "ValidateResponse"),
    ],
)
def test_pipe_code_endpoints_declare_response_schema(path, method, expected):
    """pipe-codes 的生成/验证必须在 OpenAPI 里有响应 schema。

    这两个曾是 7 个前端待接模块里**唯一**没有任何响应 schema 的端点，
    导致 `pcs-frontend` 无法为其生成类型。

    断言的是「OpenAPI 里有没有这个 schema」这个**有效契约**，不是某一种写法。
    FastAPI 有两条路都能推出它：`response_model=` 装饰器参数，或返回类型注解
    `-> GenerateResponse`。本项目写端点通常**两个都有**（house style）。
    实测：只撤掉装饰器、留着注解 → 本测试仍绿（那是正确的，契约没破）；
    两个都撤 → 转红。所以别把这测试当成「装饰器在不在」的检查。
    """
    from app.main import app

    paths = app.openapi()["paths"]
    assert path in paths, f"{path} 不在 OpenAPI 里"
    got = _response_schema_name(paths, path, method)
    assert got == expected, f"{method.upper()} {path} 的响应 schema 是 {got}，应为 {expected}"


def test_response_schema_is_registered_in_components():
    """声明的 schema 必须真的进 components.schemas，否则前端拿不到定义。"""
    from app.main import app

    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    for name, required in (
        ("GenerateResponse", {"code"}),
        ("ValidateResponse", {"valid", "errors", "segments"}),
    ):
        assert name in schemas, f"{name} 不在 components.schemas"
        assert required <= set(schemas[name].get("properties", {})), (
            f"{name} 缺字段 {required - set(schemas[name].get('properties', {}))}"
        )
