"""P6-6B T12: ``compound_delta_h_vap_natural_gas`` CONFIG 表（OPEN-P6-6A-5 关闭）。

依据 P6-6B 计划 Task 12 + brief（2026-09-27）：

- 单张 CONFIG 元数据表（``compound_delta_h_vap_natural_gas``），存 2 行
  ΔH_vap 蒸发潜热（natural gas 路径，PSV C-21 fire case）：
  - ``TYPICAL_2260``：GPSA §3.4 typical natural gas ΔH_vap = 2260 kJ/kg
    （向后兼容默认口径，OPEN-P6-6A-5 Ruling 14 back-compat）；
  - ``XLS_CONVENTION_208``：XLS PR-025 隐式 ΔH_vap = 208 kJ/kg（liquefied
    natural gas 口径；OPEN-P6-6A-5 Ruling 9/14 关闭此 OPEN 项）。
- 本批落 ORM + alembic + seed + service 双字段切换
  （``use_xls_convention: bool = False``），默认行为不变（2260 保留，
  向后兼容现有 api2000 calculations）。

设计要点：

- 字段定义严格对齐
  ``app/models/config.py:CompoundDeltaHVapNaturalGas`` ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_6b_seed_delta_h_vap.py`` 单独执行；本迁移只负责 DDL。

DOWN-REVISION = ``p6_6b_009_glycol_dehydration_full_system``（P6-6B T9）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_6b_012_delta_h_vap"
down_revision = "p6_6b_009_glycol_dehydration_full_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_delta_h_vap_natural_gas`` 表（C-21 fire case ΔH_vap 双 surface）。

    字段定义严格对齐
    ``app/models/config.py:CompoundDeltaHVapNaturalGas``。
    """
    op.create_table(
        "compound_delta_h_vap_natural_gas",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "convention", sa.String(length=32), nullable=False,
            comment='口径标识 UNIQUE："TYPICAL_2260" / "XLS_CONVENTION_208"',
        ),
        sa.Column(
            "dh_vap_kj_kg", sa.Float(), nullable=False,
            comment="ΔH_vap 蒸发潜热（kJ/kg；GPSA §3.4 / XLS PR-025 implicit）",
        ),
        sa.Column(
            "notes", sa.String(length=256), nullable=True,
            comment="工程备注（GPSA / XLS 隐式口径溯源）",
        ),
        sa.Column(
            "source", sa.String(length=128), nullable=False,
            comment='数据来源；本批填 "GPSA §3.4 typical + XLS PR-025 implicit"',
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
            "convention",
            name="uq_compound_delta_h_vap_natural_gas_convention",
        ),
    )
    op.create_index(
        "ix_compound_delta_h_vap_natural_gas_convention",
        "compound_delta_h_vap_natural_gas",
        ["convention"],
        unique=True,
    )


def downgrade() -> None:
    """删除 ``compound_delta_h_vap_natural_gas`` 表（T12 测试 / 回滚用）。"""
    op.drop_index(
        "ix_compound_delta_h_vap_natural_gas_convention",
        table_name="compound_delta_h_vap_natural_gas",
    )
    op.drop_table("compound_delta_h_vap_natural_gas")