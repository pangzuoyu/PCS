"""P3.x SIM-31: streams 表 2 个液相字段（ORM 列） + 3 个 JSONB 字段。

spec §1.2.1 + ADD-001 §3.5：

ORM 列（查询/索引需求，对称已有 vapor_fraction/api_gravity）：
- liquid_fraction: Float, nullable
- specific_gravity: Float, nullable

JSONB（stream_properties_json 内字段，展示为主，不常查询）：
- std_liq_density
- liquid_mass_rate
- liq_actual_m3hr

JSONB 字段不入 ORM 列；通过 `stream_properties_json` JSONB 容器读写，
避免 alembic 单列迁移开销。

Revision ID: p3sim_streams_liquid_fields
Revises: p3sim_streams_sim_fields
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p3sim_streams_liquid_fields"
down_revision = "p3sim_streams_sim_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """streams 液相对称 2 字段 + 索引（P3.x SIM-31 / spec §1.2.1）。

    步骤：
    - liquid_fraction Float NULL：液相分率（0~1），对称 vapor_fraction
    - specific_gravity Float NULL：比重（water=1.0），对称 api_gravity
    - ix_streams_liquid_fraction 索引（液相分率过滤，与 vapor_fraction 查询模式对称）

    不入 ORM：std_liq_density / liquid_mass_rate / liq_actual_m3hr 仍走
    stream_properties_json JSONB 容器（避免 alembic 单列迁移开销）。

    业务：液相物性对称气相模式；下游 SIM-2/3 计算与 UI 展示对齐 spec V1.1
    §变更 7 物性字段命名规范。
    """
    # SIM-31: 液相对称字段（与 vapor_fraction / api_gravity 对齐）
    op.add_column(
        "streams",
        sa.Column(
            "liquid_fraction",
            sa.Float(),
            nullable=True,
            comment="SIM-31 §1.2.1: 液相分率 (0~1)，对称 vapor_fraction",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "specific_gravity",
            sa.Float(),
            nullable=True,
            comment="SIM-31 §1.2.1: 比重（water=1.0），对称 api_gravity",
        ),
    )

    # 索引（按液相分率过滤；与 vapor_fraction 查询模式对称）
    op.create_index("ix_streams_liquid_fraction", "streams", ["liquid_fraction"])


def downgrade() -> None:
    op.drop_index("ix_streams_liquid_fraction", table_name="streams")
    op.drop_column("streams", "specific_gravity")
    op.drop_column("streams", "liquid_fraction")
