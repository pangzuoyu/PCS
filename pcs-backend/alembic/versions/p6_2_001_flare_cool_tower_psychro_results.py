"""P6-2 Task 18: flare_system_results / cooling_tower_results / psychro_results 表重构.

按 P6 计划 §Task 18 硬性：

- 3 张 CONFIG 计算结果表（flare_system_results / cooling_tower_results /
  psychro_results）从 P5-0-4a 后的 v3_1 stub（PK + input_json + output_json +
  mixin 全套）重构为 P6-2 业务字段平铺 + JSONB 容器双轨。

**DROP + CREATE** 模式（原因）：
1. 现有 3 张表 stub 仅 3-4 业务列（input_json / output_json / PK；
   psychro 多了 calc_type），与 P6-2 完整业务字段集相差 12-15 列。
2. P6-2 业务字段均为 nullable 默认值，不涉及既有数据回填。
3. P5-0-4a 之后这三表零业务数据（pcs_test 验证 COUNT(*) = 0），
   drop+create 无数据丢失风险。

**3 表净增业务字段**：
- flare_system_results: standard_profile_code + calc_type + 12 平铺列 +
  radiation_check_json（PCS-DICT-005 §3.1）
- cooling_tower_results: standard_profile_code + calc_type + tower_type +
  5 平铺列 + data_sheet_json（PCS-DICT-007 SUP-012 14 子结构）
- psychro_results: standard_profile_code + calc_type + coolprop_version +
  7 平铺列

**3 表索引**（与现有 stub 表一致 + 新增）：
- ix_*_project_id / ix_*_workspace_id / ix_*_sign_status（mixin 既有）
- uq_*_tag_per_project（project_id, tag_number）UNIQUE（P5-0-4a 决策；与
  column_sizing 同样式）
- ix_*_created_at（时间序扫描）

**字段标准**：
- standard_profile_code String(16)（C-07 锁定；与 cv_result / restriction_result
  / vessel_result / psv_result 一致）；3 表各自 default =
  API_521 / CTI_ATC_105 / ASHRAE_FUND_2021。
- mixin 全套（TaggedRecordMixin = RecordMixin + tag_number NOT NULL）：
  sign_status / record_hash / approval_* / change_* / obsoleted_* / reversal_* /
  stale_resolution_path / hash_changed / changed_fields / project_id /
  workspace_id / created_by / created_at / updated_at。

**DOWN-REVISION** = p6_2_gate_03_cepci_seed（Task 17 末态 alembic head）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p6_2_001_flare_cool_tower_psychro_results"
down_revision = "p6_2_gate_03_cepci_seed"
branch_labels = None
depends_on = None


# recordsignstatus enum 复用（P3.2 SIM-13 已创建；create_type=False 复用）
_recordsignstatus_enum = postgresql.ENUM(
    "DRAFT", "IN_APPROVAL", "CHECKED", "CHECK_REJECTED", "STALE",
    "CHANGE_PENDING", "CHANGED", "REVERSAL_PENDING", "OBSOLETE",
    name="recordsignstatus",
    create_type=False,
)


def _mixin_columns() -> list[sa.Column]:
    """TaggedRecordMixin + RecordMixin + TimestampMixin 全套列.

    不含 PK；不含 UNIQUE / FK 约束（由调用方独立声明）。
    顺序：tag_number → sign_status → record_hash → 审计列 → declared_attr FK 列 →
    时间戳。
    """
    return [
        # === TaggedRecordMixin（tag_number NOT NULL）===
        sa.Column(
            "tag_number", sa.String(length=50), nullable=False,
            comment="位号（业务子结构；TaggedRecordMixin 强制 NOT NULL）",
        ),
        # === RecordMixin sign_status + record_hash + 审计列 ===
        sa.Column(
            "sign_status",
            _recordsignstatus_enum,
            nullable=False,
            server_default=sa.text("'DRAFT'::recordsignstatus"),
            comment="记录门禁 9 态（SUP-007 §3.1）",
        ),
        sa.Column(
            "record_hash", sa.String(length=64), nullable=False,
            comment="SHA-256，数值规范化舍入 6 位有效数字，仅设计参数参与；未计算时空串",
        ),
        sa.Column("approval_step", sa.Integer(), nullable=True,
                   comment="IN_APPROVAL 当前步骤(1-based)"),
        sa.Column("approval_depth", sa.Integer(), nullable=False,
                   comment="该记录类型批准深度快照(1-4)，默认最低 1"),
        sa.Column("approval_role", sa.String(length=30), nullable=True,
                   comment="当前待批角色 ApprovalRole"),
        sa.Column("locked_by_deliverable", sa.Boolean(), nullable=False,
                   comment="被交付物快照绑定即锁定"),
        sa.Column("change_pending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_resolved_by", sa.String(length=64), nullable=True),
        sa.Column("change_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_abandoned_reason", sa.String(length=500), nullable=True),
        sa.Column("obsoleted_reason", sa.String(length=200), nullable=True),
        sa.Column("obsoleted_by", sa.Uuid(), nullable=True),
        sa.Column("obsoleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "obsoleted_via_deliverable_id", sa.Uuid(), nullable=True,
            comment="已绑定记录经 RECORD_CANCELLATION 变更单弃用",
        ),
        sa.Column("reversal_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_requested_by", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.Column("reversal_approved_by", sa.Uuid(), nullable=True),
        sa.Column("reversal_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_resolution_path", sa.String(length=30), nullable=True,
                   comment="STALE 后走的重算路径（CIA 审计）"),
        sa.Column("hash_changed", sa.Boolean(), nullable=True,
                   server_default=sa.text("FALSE"),
                   comment="record_hash 相对上版是否实质变化"),
        sa.Column("changed_fields", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="实质变化字段清单（6 位规范化后仍发散的字段）"),
        # === RecordMixin declared_attr：project_id / workspace_id ===
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        # === TimestampMixin ===
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                   server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _flare_biz_columns() -> list[sa.Column]:
    """flare_system_results 业务字段（不含 PK / mixin)."""
    return [
        # 溯源
        sa.Column(
            "standard_profile_code", sa.String(length=16), nullable=False,
            server_default=sa.text("'API_521'"),
            comment="API_521（SPEC §3.2.3 默认；C-07 String(16) 锁定）",
        ),
        sa.Column(
            "calc_type", sa.String(length=32), nullable=False,
            comment="RELIEF_SUMMARY/HEADER_SIZING/KOD_SIZING/STACK_HEIGHT/RADIATION/FLARE_TIP",
        ),
        # 结果（平铺字段）
        sa.Column("total_relief_load_kg_h", sa.Float(), nullable=True, comment="kg/h"),
        sa.Column("header_diameter_mm", sa.Float(), nullable=True, comment="mm"),
        sa.Column("header_mach", sa.Float(), nullable=True, comment="马赫数"),
        sa.Column("header_pressure_drop_kpa", sa.Float(), nullable=True, comment="kPa"),
        sa.Column("kod_diameter_mm", sa.Float(), nullable=True, comment="mm"),
        sa.Column("water_seal_height_mm", sa.Float(), nullable=True, comment="mm"),
        sa.Column("stack_height_m", sa.Float(), nullable=True, comment="m"),
        sa.Column("stack_diameter_m", sa.Float(), nullable=True, comment="m"),
        sa.Column("radiation_at_grade_kw_m2", sa.Float(), nullable=True, comment="kW/m²"),
        sa.Column("radiation_limit_kw_m2", sa.Float(), nullable=True, comment="kW/m²"),
        sa.Column("pass", sa.Boolean(), nullable=True,
                   comment="辐射校验 PASS/FAIL（SPEC §3.2.3）"),
        sa.Column("flare_tip_diameter_mm", sa.Float(), nullable=True, comment="mm"),
        sa.Column("steam_for_smokeless_kg_h", sa.Float(), nullable=True, comment="kg/h"),
        # JSONB 容器
        sa.Column("radiation_check_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="PCS-DICT-005 §3.1 辐射校验完整产物"),
        sa.Column("input_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="入参（业务子结构）"),
        sa.Column("output_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="出参（业务子结构）"),
    ]


def _cool_tower_biz_columns() -> list[sa.Column]:
    """cooling_tower_results 业务字段（不含 PK / mixin).

    业务：COOL_TOWER 冷却塔 — SPEC §3.2.4 + PCS-DICT-007 SUP-012 14 子结构。
    """
    return [
        # 溯源
        sa.Column(
            "standard_profile_code", sa.String(length=16), nullable=False,
            server_default=sa.text("'CTI_ATC_105'"),
            comment="CTI_ATC_105（SPEC §3.2.4 默认；C-07 String(16) 锁定）",
        ),
        sa.Column(
            "calc_type", sa.String(length=32), nullable=False,
            comment="MERKEL/WATER_BALANCE/FAN_POWER/HEAT_AGGREGATE",
        ),
        sa.Column(
            "tower_type", sa.String(length=32), nullable=True,
            comment="COUNTERFLOW_MECH/CROSSFLOW_MECH/NATURAL_DRAFT",
        ),
        # 结果（5 平铺字段 + SUP-012 §3）
        sa.Column("duty_kw", sa.Float(), nullable=True, comment="kW"),
        sa.Column("water_flow_m3h", sa.Float(), nullable=True, comment="m³/h"),
        sa.Column("makeup_water_m3h", sa.Float(), nullable=True, comment="m³/h"),
        sa.Column("fan_power_kw", sa.Float(), nullable=True, comment="kW"),
        sa.Column("merkel_integral", sa.Float(), nullable=True,
                   comment="Merkel 积分值"),
        # JSONB
        sa.Column("data_sheet_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="PCS-DICT-007 SUP-012 §3 14 子结构 data sheet"),
        sa.Column("input_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="入参（业务子结构）"),
        sa.Column("output_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="出参（业务子结构）"),
    ]


def _psychro_biz_columns() -> list[sa.Column]:
    """psychro_results 业务字段（不含 PK / mixin).

    业务：PSYCHRO 湿空气 — SPEC §3.2.5 + CoolProp HumidAir 包装。
    """
    return [
        # 溯源
        sa.Column(
            "standard_profile_code", sa.String(length=16), nullable=False,
            server_default=sa.text("'ASHRAE_FUND_2021'"),
            comment="ASHRAE_FUND_2021（SPEC §3.2.5 默认；C-07 String(16) 锁定）",
        ),
        sa.Column(
            "calc_type", sa.String(length=32), nullable=False,
            comment="HUMIDITY_RATIO/DEW_POINT/WET_BULB/ENTHALPY/SPECIFIC_VOLUME/COOLING_COIL",
        ),
        sa.Column(
            "coolprop_version", sa.String(length=16), nullable=True,
            comment="CoolProp 版本（如 6.6.0）；record_hash 反射自动含",
        ),
        # 结果（6 calc_type 各自的 result float + cooling_coil 双轨）
        sa.Column("humidity_ratio_kg_kg", sa.Float(), nullable=True, comment="kg/kg"),
        sa.Column("dew_point_c", sa.Float(), nullable=True, comment="°C"),
        sa.Column("wet_bulb_c", sa.Float(), nullable=True, comment="°C"),
        sa.Column("enthalpy_kj_kg", sa.Float(), nullable=True, comment="kJ/kg"),
        sa.Column("specific_volume_m3_kg", sa.Float(), nullable=True, comment="m³/kg"),
        sa.Column("sensible_heat_kw", sa.Float(), nullable=True,
                   comment="显热 kW（cooling_coil）"),
        sa.Column("latent_heat_kw", sa.Float(), nullable=True,
                   comment="潜热 kW（cooling_coil）"),
        # JSONB
        sa.Column("input_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="入参（业务子结构）"),
        sa.Column("output_json", JSONB(astext_type=sa.Text()), nullable=True,
                   comment="出参（业务子结构）"),
    ]


def _create_calc_table(
    table: str,
    pk_col: sa.Column,
    biz_cols: list[sa.Column],
) -> None:
    """建表：业务字段 + mixin 全套 + 4 索引 + (project_id, tag_number) UNIQUE.

    索引（4 个）：project_id / workspace_id / sign_status / created_at。
    约束：FK(project_id) / FK(workspace_id) / UNIQUE(project_id, tag_number) /
    PK。
    """
    op.create_table(
        table,
        pk_col,
        *biz_cols,
        *_mixin_columns(),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name=op.f(f"fk_{table}_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.workspace_id"],
            name=op.f(f"fk_{table}_workspace_id_workspaces"),
        ),
        sa.UniqueConstraint(
            "project_id", "tag_number",
            name=op.f(f"uq_{table}_tag_per_project"),
        ),
        sa.PrimaryKeyConstraint(pk_col.name, name=op.f(f"pk_{table}")),
    )
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f(f"ix_{table}_project_id"), ["project_id"], unique=False,
        )
        batch_op.create_index(
            batch_op.f(f"ix_{table}_workspace_id"), ["workspace_id"], unique=False,
        )
        batch_op.create_index(
            batch_op.f(f"ix_{table}_sign_status"), ["sign_status"], unique=False,
        )
        batch_op.create_index(
            batch_op.f(f"ix_{table}_created_at"), ["created_at"], unique=False,
        )


def upgrade() -> None:
    """Drop 3 张 stub 表（if_exists 容错）+ 重建 P6-2 完整 schema + 索引.

    pcs_test 验证 3 张表 COUNT(*) = 0（2026-09-24），drop+create 无数据丢失。
    if_exists=True 让 upgrade → downgrade → upgrade 循环幂等（downgrade 已 drop，
    再 upgrade 不应再 drop 失败）。
    顺序：flare / cool_tower / psychro（与 brief 一致）。
    """
    # 1. drop 现有 stub（P5-0-4a 后的 v3_1 简化版）；if_exists 保证可重入
    op.drop_table("flare_system_results", if_exists=True)
    op.drop_table("cooling_tower_results", if_exists=True)
    op.drop_table("psychro_results", if_exists=True)

    # 2. recreate P6-2 完整 schema
    _create_calc_table(
        "flare_system_results",
        sa.Column("flare_id", sa.Uuid(), nullable=False,
                   comment="PK（DICT V3.3 §4.1）"),
        _flare_biz_columns(),
    )
    _create_calc_table(
        "cooling_tower_results",
        sa.Column("cooling_tower_id", sa.Uuid(), nullable=False,
                   comment="PK（DICT V3.3 §4.1）"),
        _cool_tower_biz_columns(),
    )
    _create_calc_table(
        "psychro_results",
        sa.Column("psychro_id", sa.Uuid(), nullable=False,
                   comment="PK（DICT V3.3 §4.1）"),
        _psychro_biz_columns(),
    )


def _v31_stub_biz_columns(with_calc_type: bool = False) -> list[sa.Column]:
    """v3_1 stub 业务列还原：input_json / output_json（psychro 另有 calc_type).

    dd47298c9c38 stub 形态 = PK + 容器列（psychro 多 calc_type）+ mixin；
    本 helper 只给容器列，mixin 由 _create_calc_table 统一追加。
    """
    cols: list[sa.Column] = []
    if with_calc_type:
        cols.append(
            sa.Column("calc_type", sa.String(length=30), nullable=False),
        )
    cols.append(
        sa.Column("input_json", JSONB(astext_type=sa.Text()), nullable=False),
    )
    cols.append(
        sa.Column("output_json", JSONB(astext_type=sa.Text()), nullable=False),
    )
    return cols


def downgrade() -> None:
    """逆序 drop 3 张 P6-2 表 + 还原 cooling_tower / psychro 两张 v3_1 stub.

    stub 形态 = dd47298c9c38 v3_1 简化版 + p5_0_4a PK rename 后状态
    （PK cooling_tower_id / psychro_id；psychro 含 calc_type），使后续
    p5_0_4a downgrade 的 PK 改回（→ ct_calc_id / psychro_calc_id）可执行
    （TODO-040 round-trip head→p3sim 锚点修复）。

    flare_system_results 在 p6_2_001 之前链上无创建者（历史 stub 仅存在于
    手工矫正过的库），不还原；upgrade 侧 if_exists=True 与此对称。
    """
    # 逆序 drop（3 张表之间无 FK）
    op.drop_table("psychro_results")
    op.drop_table("cooling_tower_results")
    op.drop_table("flare_system_results")

    # 还原 v3_1 stub（p5_0_4a 改名后 PK；psychro 多 calc_type）
    _create_calc_table(
        "cooling_tower_results",
        sa.Column(
            "cooling_tower_id", sa.Uuid(), nullable=False,
            comment="PK（DICT V3.3 §4.1；v3_1 stub 还原）",
        ),
        _v31_stub_biz_columns(),
    )
    _create_calc_table(
        "psychro_results",
        sa.Column(
            "psychro_id", sa.Uuid(), nullable=False,
            comment="PK（DICT V3.3 §4.1；v3_1 stub 还原）",
        ),
        _v31_stub_biz_columns(with_calc_type=True),
    )
