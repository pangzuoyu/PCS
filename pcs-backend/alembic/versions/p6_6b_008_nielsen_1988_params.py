"""P6-6B T8: ``compound_nielsen_1988_params`` CONFIG 表（C-18 现代水合物抑制).

依据 P6-6B 计划 Task 8 + brief（2026-09-27）：

- 单张 CONFIG 元数据表（``compound_nielsen_1988_params``），存 7 行 Nielsen
  1988 论文 Table 1 现代水合物抑制参数 A/B/C 常数
  （CH4 / C2H6 / C3H8 / I-C4H6 / N2 / CO2 / H2S）。
- 本批落 ORM + alembic + seed（**估算 A/B/C 常数**，user ruling
  2026-09-27），工艺工程师后续从 Nielsen 1988 PDF 抄录精确数值二次核对；
  ``source`` 标记 ``'Nielsen 1988 (paper Table 1, TBD engineer verify)'``，
  ``confirmed_by`` 占位 ``'P6-6B_ENG_TEAM_TBD'``。
- Hammerschmidt 1934 是默认 model，本表为 **备选 path**（``InhibitorModel.
  NIELSEN_1988``，service 集成见 commit 2）。

设计要点：

- 字段定义严格对齐 ``app/models/config.py:CompoundNielsen1988Params`` ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_6b_seed_nielsen_1988_params.py`` 单独执行；
  本迁移只负责 DDL。

DOWN-REVISION = ``p6_6b_007_hammerschmidt_K_confirm``（P6-6B T7）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_6b_008_nielsen_1988_params"
down_revision = "p6_6b_007_hammerschmidt_K_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_nielsen_1988_params`` 表（C-18 现代水合物抑制参数).

    字段定义严格对齐 ``app/models/config.py:CompoundNielsen1988Params``。
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


def downgrade() -> None:
    """删除 ``compound_nielsen_1988_params`` 表（T8 测试 / 回滚用）."""
    op.drop_index(
        "ix_compound_nielsen_1988_params_component",
        table_name="compound_nielsen_1988_params",
    )
    op.drop_table("compound_nielsen_1988_params")