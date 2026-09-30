"""P6-3 cost_correlations CONFIG 表（SPEC §3.2.8 第三项).

依据：

- P6 计划 §Task 35（cost_est 3 模块 + cost_correlations CONFIG）。
- 镜像 P6-2 G-03 / P6-3 G-04/05/06 模式（commit ``a64b00a`` Task 17 +
  Task 29 / p6_3_001）。

设计要点：

- 单张 CONFIG 元数据表（``cost_correlations``），存成本关联式
  ``cost = a + b · S^n`` 的系数 / 指数 / 有效区间 / 基准年份；被
  ``app/services/cost_est/cost_correlation_lookup.py`` 读取做
  设备类型 → cost 估算。
- 字段定义严格对齐 ``app/models/config.py:CostCorrelationLibrary``
  ORM class（含 Float / 整型 / Numeric / String / Uuid FK + 唯一
  约束 + 2 个 CHECK 约束）。
- 不继承 ``TaggedRecordMixin`` / ``record_hash``（元数据表非业务
  计算记录）。
- 录入操作由 ``scripts/p6_3_seed_cost_correlations.py`` 单独执行
  （upsert），本迁移只负责 DDL。

DOWN-REVISION = ``p6_3_004_filtration_audit_columns``（Task 34 末态
alembic head）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_3_005_cost_correlations_library"
down_revision = "p6_3_004_filtration_audit_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``cost_correlations`` 表（SPEC §3.2.8 第三项).

    字段定义严格对齐 ``app/models/config.py:CostCorrelationLibrary``。
    """
    op.create_table(
        "cost_correlations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("equipment_type", sa.String(length=32), nullable=False),
        sa.Column(
            "version",
            sa.String(length=16),
            nullable=False,
            server_default="v1",
        ),
        sa.Column("coefficient_a", sa.Numeric(18, 2), nullable=False),
        sa.Column("coefficient_b", sa.Numeric(18, 2), nullable=False),
        sa.Column("scaling_exponent_n", sa.Numeric(6, 4), nullable=False),
        sa.Column("scale_unit", sa.String(length=16), nullable=False),
        sa.Column("valid_range_low", sa.Numeric(12, 4), nullable=False),
        sa.Column("valid_range_high", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "base_currency",
            sa.String(length=8),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "base_year",
            sa.Integer(),
            nullable=False,
            server_default="2019",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "equipment_type",
            "version",
            name="uq_cost_corr_type_version",
        ),
        sa.CheckConstraint(
            "scaling_exponent_n > 0 AND scaling_exponent_n <= 1.5",
            name="chk_cost_corr_n",
        ),
        sa.CheckConstraint(
            "coefficient_b >= 0",
            name="chk_cost_corr_b_nonneg",
        ),
    )


def downgrade() -> None:
    """删除 ``cost_correlations`` 表（Task 35 测试 / 回滚用）."""
    op.drop_table("cost_correlations")
