"""P7 Sprint 2 T1: utility_power_items 表（电耗设备清单).

依据：

- P7-OPEN-009 §1 迁移范围 #1 + §3 工时表 (0.5 天)
- P7 SPEC V1.4 §3.2.2（5）+ §4.6 + P7-OPEN-009 验收基准
- P6-5+ 既有 util_results 单表 JSONB 容器（向后兼容保留）

设计要点：

- 单张 utility_power_items 表存电耗设备清单（PUMP / COMPRESSOR / FAN 等
  旋转设备的电机功率 + 年运行小时 + 负荷率 → 年用电量）。
- 4 业务字段：motor_power_kw / operating_hours_per_year / load_factor /
  annual_consumption_kwh + 4 CHECK 约束（数值范围）。
- FK equipment_id → equipment_list.equipment_id（nullable：PMS 录入的
  早期数据可能未关联到 equipment_list 主表）。
- UNIQUE(project_id, equipment_tag) 防重复录入。
- 不继承 TaggedRecordMixin（公用工程记录，非业务计算 tagged 记录）。

DOWN-REVISION = ``p7_open_009_t0_config_energy_conversion_factors``.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_001_utility_power_items"
down_revision = "p7_open_009_t0_config_energy_conversion_factors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 utility_power_items 表 (P7 Sprint 2 T1 / P7-OPEN-009 §1 #1).

    字段定义严格对齐 app/models/util.py:UtilityPowerItem ORM class.
    """
    op.create_table(
        "utility_power_items",
        sa.Column(
            "id", sa.Uuid(),
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
            comment="设备 ID (FK equipment_list.equipment_id; nullable: PMS 早期数据可能未关联)",
        ),
        sa.Column(
            "equipment_tag", sa.String(length=64), nullable=False,
            comment="设备位号 (项目内唯一)",
        ),
        sa.Column(
            "motor_power_kw", sa.Float(), nullable=False,
            comment="电机额定功率 (kW; PUMP AbsorbedPower)",
        ),
        sa.Column(
            "operating_hours_per_year", sa.Float(), nullable=False,
            comment="年运行小时数 (h/yr; ≤ 8760)",
        ),
        sa.Column(
            "load_factor", sa.Float(), nullable=False,
            comment="负荷率 (无量纲; 0 < load_factor ≤ 1)",
        ),
        sa.Column(
            "annual_consumption_kwh", sa.Float(), nullable=False,
            comment="年用电量 (kWh/yr; = motor_power × hours × load_factor)",
        ),
        sa.Column(
            "source", sa.String(length=32), nullable=False,
            server_default="MANUAL",
            comment='数据来源: PMS (设备管理系统) / MANUAL (手动录入) / CALC (计算)',
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
            comment="记录创建时间 (DB server_default)",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间 (ORM onupdate 触发)",
        ),
        sa.CheckConstraint(
            "motor_power_kw > 0",
            name="ck_utility_power_items_motor_power_positive",
        ),
        sa.CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_power_items_hours_in_year",
        ),
        sa.CheckConstraint(
            "load_factor > 0 AND load_factor <= 1",
            name="ck_utility_power_items_load_factor_range",
        ),
        sa.CheckConstraint(
            "annual_consumption_kwh >= 0",
            name="ck_utility_power_items_consumption_non_negative",
        ),
        sa.UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_power_items_project_equipment_tag",
        ),
    )
    op.create_index(
        "ix_utility_power_items_project",
        "utility_power_items",
        ["project_id"],
    )
    op.create_index(
        "ix_utility_power_items_workspace",
        "utility_power_items",
        ["workspace_id"],
    )


def downgrade() -> None:
    """删除 utility_power_items 表 (T1 测试 / 回滚用)."""
    op.drop_index("ix_utility_power_items_workspace", table_name="utility_power_items")
    op.drop_index("ix_utility_power_items_project", table_name="utility_power_items")
    op.drop_table("utility_power_items")
