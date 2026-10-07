"""P7 Sprint 2 T5: utility_energy_summary 表 (综合能耗汇总).

依据:

- P7-OPEN-009 §1 迁移范围 #4 + §3 工时表 (1.0 天)
- P7 SPEC V1.4 §3.2.2(5) + §4.6 + P7-OPEN-009 验收基准
- P7-OPEN-009 §6 验收: 综合能耗汇总与 Excel 偏差 ≤ 2%
- P7-OPEN-009 §6.3: 折标煤系数 from config_energy_conversion_factors
- D1 裁决 1A: 5 表权威 + JSONB deprecated

设计要点:

- 单张 utility_energy_summary 表存项目年度综合能耗汇总 (折标油 / 标煤)。
- 业务字段:
  - 6 类能源 annual 消耗 (electricity_kwh_yr / fuel_gas_nm3_yr /
    steam_t_yr / water_t_yr / gas_nm3_yr / low_temp_heat_gj_yr)
    nullable (T1/T2/T3 + 冷却水子表聚合; cooling_water 待 P7-6B 落地)
  - 3 用户 spec 字段 (annual_total_energy / toe_conversion_factor /
    standard_coal_factor) + 2 derived (total_toe / total_standard_coal_kg)
  - 容差校验 2 字段 (tolerance_pct / tolerance_status enum OK/EXCEEDED)
  - 时间戳: business_year / computed_at / created_at / updated_at
- 聚合 service 集成 ConfigEnergyConversionFactor 折标系数 (5-min TTL 缓存)。
- FK project_id / workspace_id (CASCADE).
- UNIQUE(project_id, business_year, source) 防重复录入同源同年汇总。
- 5 CHECK 约束 (consumption_i >= 0, total_toe >= 0, etc.).

DOWN-REVISION = ``p7_open_009_004_auxiliary_consumption_4fields``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_005_utility_energy_summary"
down_revision = "p7_open_009_004_auxiliary_consumption_4fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 utility_energy_summary 表 (P7 Sprint 2 T5 / P7-OPEN-009 §1 #4).

    字段定义严格对齐 app/models/util.py:UtilityEnergySummary ORM class.
    """
    op.create_table(
        "utility_energy_summary",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            comment="UUID 主键 (uuid.uuid4 default)",
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.project_id", ondelete="CASCADE"),
            nullable=False,
            comment="项目 ID (FK projects.project_id)",
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.workspace_id", ondelete="CASCADE"),
            nullable=False,
            comment="工作区 ID (FK workspaces.workspace_id)",
        ),
        sa.Column(
            "business_year",
            sa.Integer(),
            nullable=False,
            comment="业务年度 (e.g., 2026; summary 是 annual aggregation)",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="CALCULATION",
            comment="数据来源: CALCULATION (服务计算) / XLS_REFERENCE (Excel 对账基准)",
        ),
        sa.Column(
            "electricity_kwh_yr",
            sa.Float(),
            nullable=True,
            comment="年用电量 (kWh/yr; 聚合 utility_power_items.annual_consumption_kwh)",
        ),
        sa.Column(
            "fuel_gas_nm3_yr",
            sa.Float(),
            nullable=True,
            comment="年燃料气消耗量 (Nm³/yr; 聚合 utility_fuel_gas.annual_consumption_nm3)",
        ),
        sa.Column(
            "steam_t_yr",
            sa.Float(),
            nullable=True,
            comment="年蒸汽消耗量 (t/yr; 聚合 utility_heat_exchange.annual_consumption_t)",
        ),
        sa.Column(
            "water_t_yr",
            sa.Float(),
            nullable=True,
            comment="年新鲜水消耗量 (t/yr; 待 P7-6B 冷却水子表落地后聚合)",
        ),
        sa.Column(
            "gas_nm3_yr",
            sa.Float(),
            nullable=True,
            comment="年工艺气体消耗量 (Nm³/yr; 预留字段; 待子表工艺团队细化)",
        ),
        sa.Column(
            "low_temp_heat_gj_yr",
            sa.Float(),
            nullable=True,
            comment="年低温余热 (GJ/yr; 预留字段; 待工艺团队细化)",
        ),
        sa.Column(
            "annual_total_energy",
            sa.Float(),
            nullable=False,
            comment=(
                "年度总能耗 (MJ/yr; canonical unit; "
                "= sum(consumption_i × unit_to_mj_factor_i))"
            ),
        ),
        sa.Column(
            "toe_conversion_factor",
            sa.Float(),
            nullable=False,
            comment=(
                "聚合折标油系数 (kg 标油/MJ; "
                "= total_toe × 1000 / annual_total_energy)"
            ),
        ),
        sa.Column(
            "standard_coal_factor",
            sa.Float(),
            nullable=False,
            comment=(
                "聚合折标煤系数 (kg 标煤/MJ; "
                "= total_standard_coal_kg / annual_total_energy)"
            ),
        ),
        sa.Column(
            "total_toe",
            sa.Float(),
            nullable=False,
            comment="年度折标油总量 (tonne oil equivalent)",
        ),
        sa.Column(
            "total_standard_coal_kg",
            sa.Float(),
            nullable=False,
            comment="年度折标煤总量 (kg 标煤)",
        ),
        sa.Column(
            "tolerance_pct",
            sa.Float(),
            nullable=True,
            comment="容差 (vs XLS_REFERENCE source; ≤2% per P7-OPEN-009 §6)",
        ),
        sa.Column(
            "tolerance_status",
            sa.String(length=16),
            nullable=False,
            server_default="OK",
            comment="容差校验状态: OK (≤2%) / EXCEEDED (>2%) / NA (无 XLS 参考)",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="服务计算时间 (DB server_default)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="记录创建时间 (DB server_default)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="记录更新时间 (ORM onupdate 触发)",
        ),
        sa.CheckConstraint(
            "annual_total_energy >= 0",
            name="ck_utility_energy_summary_total_non_negative",
        ),
        sa.CheckConstraint(
            "toe_conversion_factor > 0",
            name="ck_utility_energy_summary_toe_factor_positive",
        ),
        sa.CheckConstraint(
            "standard_coal_factor > 0",
            name="ck_utility_energy_summary_coal_factor_positive",
        ),
        sa.CheckConstraint(
            "total_toe >= 0",
            name="ck_utility_energy_summary_total_toe_non_negative",
        ),
        sa.CheckConstraint(
            "total_standard_coal_kg >= 0",
            name="ck_utility_energy_summary_total_coal_non_negative",
        ),
        sa.CheckConstraint(
            "tolerance_status IN ('OK', 'EXCEEDED', 'NA')",
            name="ck_utility_energy_summary_tolerance_status_enum",
        ),
        sa.UniqueConstraint(
            "project_id", "business_year", "source",
            name="uq_utility_energy_summary_project_year_source",
        ),
    )
    op.create_index(
        "ix_utility_energy_summary_project",
        "utility_energy_summary",
        ["project_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_utility_energy_summary_workspace",
        "utility_energy_summary",
        ["workspace_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_utility_energy_summary_year",
        "utility_energy_summary",
        ["business_year"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """删除 utility_energy_summary 表 (T5 测试 / 回滚用)."""
    op.drop_index(
        "ix_utility_energy_summary_year", table_name="utility_energy_summary",
        if_exists=True,
    )
    op.drop_index(
        "ix_utility_energy_summary_workspace", table_name="utility_energy_summary",
        if_exists=True,
    )
    op.drop_index(
        "ix_utility_energy_summary_project", table_name="utility_energy_summary",
        if_exists=True,
    )
    op.drop_table("utility_energy_summary", if_exists=True)
