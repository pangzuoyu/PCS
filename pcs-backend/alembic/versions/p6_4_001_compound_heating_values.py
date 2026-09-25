"""P6-4 compound_heating_values CONFIG 表（C-06 气体热值 / SPEC §3.2.3.6）。

依据：

- P6 计划 §Task 1（C-06 气体热值；2 天）。
- 镜像 P6-2 G-03 / P6-3 G-04/05/06 模式（commit ``a64b00a`` Task 17 +
  Task 29 / p6_3_001 / p6_3_005）；新增第 6 张元数据型 CONFIG 表。

设计要点：

- 单张 CONFIG 元数据表（``compound_heating_values``），存 64 种化合物的
  HHV/LHV（GPSA FIG. 23-2 合成数据占位；工艺室签字后替换为真实期号）。
- 字段定义严格对齐 ``app/models/config.py:CompoundHeatingValues``
  ORM class（含 Float / 整型 / String / DateTime + UNIQUE 索引 cas）。
- 不继承 ``TaggedRecordMixin`` / ``record_hash``（元数据表非业务
  计算记录）。
- 录入操作由 ``scripts/p6_4_gate_03_compound_heating_values_seed.py``
  单独执行（先 DELETE 后 INSERT 幂等）；本迁移只负责 DDL。

DOWN-REVISION = ``p6_3_005_cost_correlations_library``（P6-3 末态
alembic head；2026-09-25 由 Task 35 提交）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_4_001_compound_heating_values"
down_revision = "p6_3_005_cost_correlations_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_heating_values`` 表（C-06 气体热值 / SPEC §3.2.3.6）。

    字段定义严格对齐 ``app/models/config.py:CompoundHeatingValues``。
    """
    op.create_table(
        "compound_heating_values",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "cas", sa.String(length=16), nullable=False,
            comment="CAS 注册号（UNIQUE 索引）；如 '74-82-8' = methane",
        ),
        sa.Column(
            "name", sa.String(length=64), nullable=False,
            comment="物质名（如 'methane' / 'H2S' / 'n-butane'）",
        ),
        sa.Column(
            "hhv_mj_kg", sa.Float(), nullable=False,
            comment="高位热值 HHV（MJ/kg；liquid H2O 生成条件）",
        ),
        sa.Column(
            "lhv_mj_kg", sa.Float(), nullable=False,
            comment="低位热值 LHV（MJ/kg；gaseous H2O 生成条件）",
        ),
        sa.Column(
            "mw_g_mol", sa.Float(), nullable=False,
            comment="分子量（g/mol；用于组分加权计算）",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "GPSA_ED13_FIG23-2"',
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
        sa.UniqueConstraint("cas", name="uq_compound_heating_values_cas"),
    )
    # cas 已 inline index=True 在 ORM；为支持 HHV/LHV 数值范围查询另建
    # 普通索引（non-UNIQUE），便于 SELECT WHERE hhv_mj_kg BETWEEN ...
    op.create_index(
        "ix_compound_heating_values_hhv",
        "compound_heating_values",
        ["hhv_mj_kg"],
    )


def downgrade() -> None:
    """删除 ``compound_heating_values`` 表（Task 1 测试 / 回滚用）。"""
    op.drop_index(
        "ix_compound_heating_values_hhv",
        table_name="compound_heating_values",
    )
    op.drop_table("compound_heating_values")