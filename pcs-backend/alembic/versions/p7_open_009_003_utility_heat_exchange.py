"""P7 Sprint 2 T3: utility_heat_exchange 表 (蒸汽/冷凝水).

依据：

- P7-OPEN-009 §1 迁移范围 #3 + §3 工时表 (0.5 天)
- P7 SPEC V1.4 §3.2.2(5) + §4.6 + P7-OPEN-009 验收基准
- P7-OPEN-009 §1: steam_pressure / steam_quality / return_condensate
  3 字段 + 温度等级分类

设计要点：

- 单张 utility_heat_exchange 表存蒸汽 (HP/MP/LP/ULTRA_HIGH) + 冷凝水
  消耗 / 回收数据。
- 业务字段：steam_pressure_mpa_gauge / steam_quality_pct /
  return_condensate_pct / temperature_class enum (LP/MP/HP/ULTRA_HIGH) /
  steam_consumption_t_h / annual_consumption_t + 4 CHECK 约束。
- FK equipment_id → equipment_list.equipment_id (nullable)。
- UNIQUE(project_id, equipment_tag) 防重复录入。
- 不继承 TaggedRecordMixin (公用工程记录)。

DOWN-REVISION = ``p7_open_009_002_utility_fuel_gas``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_003_utility_heat_exchange"
down_revision = "p7_open_009_002_utility_fuel_gas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 utility_heat_exchange 表 (P7 Sprint 2 T3 / P7-OPEN-009 §1 #3).

    字段定义严格对齐 app/models/util.py:UtilityHeatExchange ORM class.
    """
    op.create_table(
        "utility_heat_exchange",
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
            "equipment_id",
            sa.Uuid(),
            sa.ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"),
            nullable=True,
            comment="设备 ID (FK equipment_list.equipment_id)",
        ),
        sa.Column(
            "equipment_tag",
            sa.String(length=64),
            nullable=False,
            comment="设备位号 (项目内唯一)",
        ),
        sa.Column(
            "steam_pressure_mpa_gauge",
            sa.Float(),
            nullable=False,
            comment="蒸汽压力 (MPa gauge; LP 0.3-0.8/MP 1.0-2.5/HP 3.5-10/ULTRA_HIGH>10)",
        ),
        sa.Column(
            "steam_quality_pct",
            sa.Float(),
            nullable=False,
            comment="蒸汽干度 (% dryness; 饱和蒸汽 100, 含水蒸汽 <100; 0~100)",
        ),
        sa.Column(
            "return_condensate_pct",
            sa.Float(),
            nullable=False,
            comment="冷凝水回收率 (% condensate return; 0~100)",
        ),
        sa.Column(
            "temperature_class",
            sa.String(length=16),
            nullable=False,
            comment="蒸汽温度等级: LP (低压) / MP (中压) / HP (高压) / ULTRA_HIGH (超高压)",
        ),
        sa.Column(
            "steam_consumption_t_h",
            sa.Float(),
            nullable=False,
            comment="小时蒸汽消耗量 (t/h)",
        ),
        sa.Column(
            "operating_hours_per_year",
            sa.Float(),
            nullable=False,
            server_default="8000",
            comment="年运行小时数 (h/yr; ≤ 8760)",
        ),
        sa.Column(
            "annual_consumption_t",
            sa.Float(),
            nullable=False,
            comment="年蒸汽消耗量 (t/yr; = steam_consumption_t_h × operating_hours_per_year)",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="MANUAL",
            comment="数据来源: HEAT 汇总 / PMS / MANUAL / CALC",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="记录创建时间 (DB server_default)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="记录更新时间 (ORM onupdate 触发)",
        ),
        sa.CheckConstraint(
            "steam_pressure_mpa_gauge > 0",
            name="ck_utility_heat_exchange_pressure_positive",
        ),
        sa.CheckConstraint(
            "steam_quality_pct >= 0 AND steam_quality_pct <= 100",
            name="ck_utility_heat_exchange_quality_pct_range",
        ),
        sa.CheckConstraint(
            "return_condensate_pct >= 0 AND return_condensate_pct <= 100",
            name="ck_utility_heat_exchange_return_condensate_pct_range",
        ),
        sa.CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_heat_exchange_hours_in_year",
        ),
        sa.CheckConstraint(
            "annual_consumption_t >= 0",
            name="ck_utility_heat_exchange_annual_consumption_non_negative",
        ),
        sa.CheckConstraint(
            "temperature_class IN ('LP', 'MP', 'HP', 'ULTRA_HIGH')",
            name="ck_utility_heat_exchange_temperature_class_enum",
        ),
        sa.UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_heat_exchange_project_equipment_tag",
        ),
    )
    op.create_index(
        "ix_utility_heat_exchange_project",
        "utility_heat_exchange",
        ["project_id"],
    )
    op.create_index(
        "ix_utility_heat_exchange_workspace",
        "utility_heat_exchange",
        ["workspace_id"],
    )
    op.create_index(
        "ix_utility_heat_exchange_temperature_class",
        "utility_heat_exchange",
        ["temperature_class"],
    )


def downgrade() -> None:
    """删除 utility_heat_exchange 表 (T3 测试 / 回滚用)."""
    op.drop_index(
        "ix_utility_heat_exchange_temperature_class",
        table_name="utility_heat_exchange",
    )
    op.drop_index(
        "ix_utility_heat_exchange_workspace",
        table_name="utility_heat_exchange",
    )
    op.drop_index(
        "ix_utility_heat_exchange_project",
        table_name="utility_heat_exchange",
    )
    op.drop_table("utility_heat_exchange")