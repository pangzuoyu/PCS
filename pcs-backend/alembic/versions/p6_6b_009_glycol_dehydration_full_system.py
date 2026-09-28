"""P6-6B T9: ``glycol_dehydration_full_system`` CONFIG 表（C-16 glycol dehydration）。

依据 P6-6B 计划 Task 9 + brief（2026-09-27）：

- 单张 CONFIG 元数据表（``glycol_dehydration_full_system``），存 10 行典型
  工况范围（TEG 浓度 / reboiler temperature / stripping gas rate /
  column diameter / column height / NTU / reflux ratio / contactor
  pressure / water removal efficiency / reboiler duty）。
- 本批落 ORM + alembic + seed（**估算典型工况 min/max**，user ruling
  2026-09-27），工艺工程师后续从 GPSA Fig. 20-XX + McKetta-Wehe 二次核对；
  ``source`` 标记 ``'GPSA Fig. 20-XX + McKetta-Wehe (TBD engineer
  verify)'``，``confirmed_by`` 占位 ``'P6-6B_ENG_TEAM_TBD'``。
- PCS 当前仅 algebraic EXACT contact tower diameter（P6-6A-6 v5.1）；
  reboiler / stripping / full column / lean glycol 4 子模块
  OUT_OF_SCOPE，本表为 P6-7 服务扩展占位。

设计要点：

- 字段定义严格对齐 ``app/models/config.py:GlycolDehydrationFullSystem``
  ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_6b_seed_glycol_dehydration_full_system.py``
  单独执行；本迁移只负责 DDL。

DOWN-REVISION = ``p6_6b_008_nielsen_1988_params``（P6-6B T8）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_6b_009_glycol_dehydration_full_system"
down_revision = "p6_6b_008_nielsen_1988_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``glycol_dehydration_full_system`` 表（C-16 典型工况范围）。

    字段定义严格对齐
    ``app/models/config.py:GlycolDehydrationFullSystem``。
    """
    op.create_table(
        "glycol_dehydration_full_system",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "parameter", sa.String(length=64), nullable=False,
            comment="典型工况参数 UNIQUE：teg_concentration / "
                    "reboiler_temperature / stripping_gas_rate / "
                    "column_diameter / column_height / n_transfer_units / "
                    "reflux_ratio / contactor_pressure / "
                    "water_removal_efficiency / reboiler_duty",
        ),
        sa.Column(
            "min_value", sa.Float(), nullable=False,
            comment="数值最小值",
        ),
        sa.Column(
            "max_value", sa.Float(), nullable=False,
            comment="数值最大值",
        ),
        sa.Column(
            "unit", sa.String(length=32), nullable=False,
            comment="数值单位（wt% / °F / scf/gal TEG / ft / NTU / - / "
                    "psia / % / kBtu/hr）",
        ),
        sa.Column(
            "notes", sa.String(length=256), nullable=True,
            comment="工程备注（典型工况语境）",
        ),
        sa.Column(
            "source", sa.String(length=128), nullable=False,
            comment='数据来源；本批填 "GPSA Fig. 20-XX + McKetta-Wehe '
                    '(TBD engineer verify)"',
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
            "parameter",
            name="uq_glycol_dehydration_full_system_parameter",
        ),
    )
    op.create_index(
        "ix_glycol_dehydration_full_system_parameter",
        "glycol_dehydration_full_system",
        ["parameter"],
        unique=True,
    )


def downgrade() -> None:
    """删除 ``glycol_dehydration_full_system`` 表（T9 测试 / 回滚用）。"""
    op.drop_index(
        "ix_glycol_dehydration_full_system_parameter",
        table_name="glycol_dehydration_full_system",
    )
    op.drop_table("glycol_dehydration_full_system")
