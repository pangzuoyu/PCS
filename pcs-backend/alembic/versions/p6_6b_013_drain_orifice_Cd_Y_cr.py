"""P6-6B T13: ``drain_orifice_Cd_Y_cr`` CONFIG 表（OPEN-P6-6A-4 关闭).

依据 P6-6B 计划 Task 13 + brief（2026-09-27）：

- 单张 CONFIG 元数据表（``drain_orifice_Cd_Y_cr``），存 6 行介质 →
  （Cd / Y_cr / β range）：
  - ``NATURAL_GAS``：β=0.0~0.7, Cd=0.83932, Y_cr=0.687
    （XLS PR-023 默认）；
  - ``AIR``：β=0.0~0.7, Cd=0.84, Y_cr=0.72；
  - ``STEAM``：β=0.0~0.7, Cd=0.83, Y_cr=0.55；
  - ``WATER``：β=0.0~0.7, Cd=0.85, Y_cr=0.58；
  - ``N2``：β=0.0~0.7, Cd=0.84, Y_cr=0.72；
  - ``CO2``：β=0.0~0.7, Cd=0.83, Y_cr=0.65。
- 本批落 ORM + alembic + seed + service feature flag
  （``_USE_XLS_CD_Y_CR: bool = False``），默认行为不变（Cd=1.0 / Y_cr=1.0
  向后兼容现有 drain_orifice API 行为），需 ETL 重新对账后再开启 XLS
  convention 路径。

设计要点：

- 字段定义严格对齐 ``app/models/config.py:DrainOrificeCdYCr`` ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_6b_seed_drain_orifice_Cd_Y_cr.py`` 单独执行；
  本迁移只负责 DDL。

DOWN-REVISION = ``p6_6b_012_delta_h_vap``（P6-6B T12）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_6b_013_drain_orifice_Cd_Y_cr"
down_revision = "p6_6b_012_delta_h_vap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``drain_orifice_Cd_Y_cr`` 表（C-19 排污孔板 Cd/Y_cr lookup).

    字段定义严格对齐 ``app/models/config.py:DrainOrificeCdYCr``。
    """
    op.create_table(
        "drain_orifice_Cd_Y_cr",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "fluid", sa.String(length=16), nullable=False,
            comment='介质 UNIQUE："NATURAL_GAS" / "AIR" / "STEAM" / "WATER" / "N2" / "CO2"',
        ),
        sa.Column(
            "beta_range_min", sa.Float(), nullable=False,
            comment="β 直径比下限（无量纲；典型 0.0）",
        ),
        sa.Column(
            "beta_range_max", sa.Float(), nullable=False,
            comment="β 直径比上限（无量纲；典型 0.7）",
        ),
        sa.Column(
            "cd", sa.Float(), nullable=False,
            comment="Cd 流量系数（无量纲；XLS PR-023 + Miller 1990 取值）",
        ),
        sa.Column(
            "y_cr", sa.Float(), nullable=False,
            comment="Y_cr 临界压力比（无量纲；XLS PR-023 + Miller 1990 取值）",
        ),
        sa.Column(
            "notes", sa.String(length=256), nullable=True,
            comment="工程备注（XLS PR-023 / Miller 1990 取值溯源）",
        ),
        sa.Column(
            "source", sa.String(length=128), nullable=False,
            comment='数据来源；本批填 "XLS PR-023 + Miller (1990) discharge coefficients"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=False,
            comment='本批填 "P6-6B_ENG_TEAM"；工艺工程师二次核对后改填实际签字人',
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
            "fluid",
            name="uq_drain_orifice_Cd_Y_cr_fluid",
        ),
    )
    op.create_index(
        "ix_drain_orifice_Cd_Y_cr_fluid",
        "drain_orifice_Cd_Y_cr",
        ["fluid"],
        unique=True,
    )


def downgrade() -> None:
    """删除 ``drain_orifice_Cd_Y_cr`` 表（T13 测试 / 回滚用）."""
    op.drop_index(
        "ix_drain_orifice_Cd_Y_cr_fluid",
        table_name="drain_orifice_Cd_Y_cr",
    )
    op.drop_table("drain_orifice_Cd_Y_cr")