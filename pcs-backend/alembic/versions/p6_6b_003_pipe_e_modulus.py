"""P6-6B T3: ``pipe_e_modulus`` CONFIG 表（C-13 Joukowsky 输入）。

依据：

- P6-6B 计划 §T3 收口（8 行管材等级 E 模量；API 5L + ASTM A106/A335）。
- 镜像 p6_5_001~004 / p6_5_006 / p6_6b_001 模式（成本/物性 CONFIG 元数据表）。
- ``pipe_e_modulus`` 存 8 行管材等级 E 模量（API 5L X42/X52/X65/X70/X80
  + ASTM A106 ``A106-B`` + ASTM A335 ``A335-P11/A335-P22``），供 C-13
  PIPE_NET ``surge_pressure`` 模块 ``Wylie-Streeter`` 公式
  ``a = a_f/√(1+(K·D)/(E·e)·C₁)`` 读取。

设计要点：

- 单张 CONFIG 元数据表（``pipe_e_modulus``）。
- 字段定义严格对齐 ``app/models/config.py:PipeEModulus`` ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_6b_seed_pipe_e_modulus.py`` 单独执行；本迁移
  只负责 DDL。

DOWN-REVISION = ``p6_6b_001_compound_heating_values_confirm``（P6-6B T1）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_6b_003_pipe_e_modulus"
down_revision = "p6_6b_001_compound_heating_values_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``pipe_e_modulus`` 表（C-13 PIPE_NET 浪涌压力 E 模量）。

    字段定义严格对齐 ``app/models/config.py:PipeEModulus``。
    """
    op.create_table(
        "pipe_e_modulus",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "grade", sa.String(length=32), nullable=False,
            comment='管材等级 UNIQUE：API 5L "X42/X52/X65/X70/X80" / '
                    'ASTM A106 "A106-B" / ASTM A335 "A335-P11/A335-P22"',
        ),
        sa.Column(
            "e_psi", sa.Float(), nullable=False,
            comment="弹性模量 E（psi；典型值 70°F）；Wylie-Streeter 含管壁修正用",
        ),
        sa.Column(
            "spec_source", sa.String(length=64), nullable=False,
            comment='标准来源："API 5L" / "ASTM A106" / "ASTM A335"',
        ),
        sa.Column(
            "source", sa.String(length=128), nullable=False,
            comment='数据来源；本批填 "API 5L (2018) + ASTM A106/A335"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=False,
            comment="工艺室确认签字人",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间",
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
            "grade",
            name="uq_pipe_e_modulus_grade",
        ),
    )
    # 创建 grade 列的 UNIQUE 索引（与 UniqueConstraint 同步；OR/PG 行为对齐）
    op.create_index(
        "ix_pipe_e_modulus_grade",
        "pipe_e_modulus",
        ["grade"],
        unique=True,
    )


def downgrade() -> None:
    """删除 ``pipe_e_modulus`` 表（T3 测试 / 回滚用）。"""
    op.drop_index("ix_pipe_e_modulus_grade", table_name="pipe_e_modulus")
    op.drop_table("pipe_e_modulus")
