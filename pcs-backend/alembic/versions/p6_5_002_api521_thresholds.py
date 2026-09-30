"""P6-5 compound_api521_thresholds CONFIG 表（C-22 API 521 §5.15 致死/致伤阈值).

依据：

- P6-5 计划 Task C5 收口（4 张 CONFIG 表 + 4 alembic + 4 seed）。
- 镜像 p6_5_001 模式。
- API 521 §5.15 Table 5-15：致死 12.6 kW/m² / 致伤 4.7 kW/m²。

设计要点：

- 单张 CONFIG 元数据表（``compound_api521_thresholds``），存 2 行
  致死/致伤阈值。
- 字段定义严格对齐 ``app/models/config.py:CompoundApi521Thresholds``
  ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_5_seed_api521_thresholds.py`` 单独执行；
  本迁移只负责 DDL。

DOWN-REVISION = ``p6_5_001_pasquill_sigma``。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_5_002_api521_thresholds"
down_revision = "p6_5_001_pasquill_sigma"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_api521_thresholds`` 表（C-22 API 521 §5.15 阈值).

    字段定义严格对齐 ``app/models/config.py:CompoundApi521Thresholds``。
    """
    op.create_table(
        "compound_api521_thresholds",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "threshold_type", sa.String(length=32), nullable=False,
            comment='阈值类型 UNIQUE：如 "INJURY"/"LETHALITY"',
        ),
        sa.Column(
            "flux_kw_m2", sa.Float(), nullable=False,
            comment="允许辐射热通量（kW/m²）；API 521 §5.15 Table 5-15",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "API521_§5.15_Table_5-15"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL）",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
            comment="记录创建时间（DB server_default）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间（ORM onupdate 触发）",
        ),
        sa.UniqueConstraint(
            "threshold_type",
            name="uq_compound_api521_thresholds_type",
        ),
    )


def downgrade() -> None:
    """删除 ``compound_api521_thresholds`` 表（C5 测试 / 回滚用）."""
    op.drop_table("compound_api521_thresholds")
