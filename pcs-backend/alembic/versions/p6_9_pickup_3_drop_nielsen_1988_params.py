"""P6-9-PICKUP-3 T1: 删除 ``compound_nielsen_1988_params`` CONFIG 表.

依据 P6-9-PICKUP-3 brief（2026-11-15）：

- P6-6B T8（commit p6_6b_008）创建该表（OPEN-P6-6A-11 partial closure）。
- P6-6B 工艺室 v3 修复后，``_calculate_nielsen_depression_full``（P6-7 T3）
  + ``_NIELSEN_1988_FULL_PARAMS``（内联 7 组常数）已替代该表。
- P6-9-PICKUP-2 T5（commit ``b599420``）服务代码层 dead code 已清。
- 本迁移清理 DB 层残留：``upgrade`` 删除 ``compound_nielsen_1988_params``
  表（连同 unique 约束 + index），``downgrade`` 还原 ``p6_6b_008`` 等价
  DDL（rollback 对称需要）。

DOWN-REVISION = ``p6_6b_013_drain_orifice_Cd_Y_cr``（当前 alembic HEAD）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_9_pickup_3_drop_nielsen_1988_params"
down_revision = "p6_6b_013_drain_orifice_Cd_Y_cr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """删除 ``compound_nielsen_1988_params`` 表（T1 清理目标）."""
    op.drop_index(
        "ix_compound_nielsen_1988_params_component",
        table_name="compound_nielsen_1988_params",
    )
    op.drop_table("compound_nielsen_1988_params")


def downgrade() -> None:
    """还原 ``p6_6b_008`` 等价 DDL（rollback 对称需要).

    字段定义严格对齐 ``p6_6b_008_nielsen_1988_params.py::upgrade``。
    """
    op.create_table(
        "compound_nielsen_1988_params",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "component", sa.String(length=16), nullable=False,
            comment="组分 UNIQUE：CH4/C2H6/C3H8/I-C4H6/N2/CO2/H2S",
        ),
        sa.Column(
            "a", sa.Float(), nullable=False,
            comment="Nielsen 1988 A 常数（无量纲）",
        ),
        sa.Column(
            "b", sa.Float(), nullable=False,
            comment="Nielsen 1988 B 常数（无量纲）",
        ),
        sa.Column(
            "c", sa.Float(), nullable=False,
            comment="Nielsen 1988 C 常数（无量纲；本批估算全为 0.0）",
        ),
        sa.Column(
            "source", sa.String(length=128), nullable=False,
            comment='数据来源；本批填 '
                    '"Nielsen 1988 (paper Table 1, TBD engineer verify)"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=False,
            comment='本批填 "P6-6B_ENG_TEAM_TBD"；工艺工程师二次核对后改填实际签字人',
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL，工艺室签字后填入）",
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
            "component",
            name="uq_compound_nielsen_1988_params_component",
        ),
    )
    op.create_index(
        "ix_compound_nielsen_1988_params_component",
        "compound_nielsen_1988_params",
        ["component"],
        unique=True,
    )