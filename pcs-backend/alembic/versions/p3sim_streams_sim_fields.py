"""P3.x SIM-17+18: streams 表 8 字段扩展。

spec §3.2.4 + ADD-002 §3.6：
- SIM-17 (4 字段)：simulation_status / tear_stream / estimated / stream_properties_json
- SIM-18 (4 JSONB)：user_provided_properties_json / calculated_properties_json /
  effective_properties_json / conflict_resolutions_json

所有字段 nullable（向后兼容 P3.2 SIM 既有数据）；
索引：simulation_status（按状态过滤）+ estimated（按估算标记过滤）

Revision ID: p3sim_streams_sim_fields
Revises: p3sim_sim_unit_op_results
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p3sim_streams_sim_fields"
down_revision = "p3sim_sim_unit_op_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """streams SIM 字段扩展（P3.2 SIM-17 §3.2.4 物性来源标注）。

    步骤：
    - simulation_status (varchar 30)：SOLVED/ESTIMATED/MEASURED/MANUAL/UNKNOWN
      （区分 SIM 计算/估算/实测/人工/未知四源）
    - source_unit_op (varchar 100)：源单元操作 unit_uid（追溯到 PRO/II 单元）
    - source_stream_uid (varchar 100)：源 PRO/II 流股编号
    - sim_import_id (UUID FK→sim_imports)：本次 SIM 导入批次 ID
    - 索引：sim_import_id（按批次反查）+ (source_unit_op, source_stream_uid) 复合

    业务：streams 表新增 SIM 来源标注，与 sim_imports + sim_unit_op_results
    形成完整 SIM 血缘链（流股 → 单元 → 批次）。
    """
    # SIM-17 4 字段
    op.add_column(
        "streams",
        sa.Column(
            "simulation_status",
            sa.String(length=30),
            nullable=True,
            comment="SIM-17 §3.2.4: SOLVED/ESTIMATED/MEASURED/MANUAL/UNKNOWN",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "tear_stream",
            sa.Boolean(),
            nullable=True,
            comment="SIM-17 §3.2.4: TRUE=撕裂流（收敛循环起点）",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "estimated",
            sa.Boolean(),
            nullable=True,
            comment="SIM-17 §3.2.4: TRUE=物性被估算",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "stream_properties_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="SIM-17 §3.2.4: 流物性包",
        ),
    )

    # SIM-18 4 JSONB
    op.add_column(
        "streams",
        sa.Column(
            "user_provided_properties_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="SIM-18 §3.6: 用户提供的物性",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "calculated_properties_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="SIM-18 §3.6: SIM-3 自动补全的物性",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "effective_properties_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="SIM-18 §3.6: 实际生效的物性",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "conflict_resolutions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="SIM-18 §3.6: 冲突解决记录",
        ),
    )

    # 索引（SIM-21/SIM-27 查询加速）
    op.create_index("ix_streams_simulation_status", "streams", ["simulation_status"])
    op.create_index("ix_streams_estimated", "streams", ["estimated"])


def downgrade() -> None:
    op.drop_index("ix_streams_estimated", table_name="streams")
    op.drop_index("ix_streams_simulation_status", table_name="streams")
    op.drop_column("streams", "conflict_resolutions_json")
    op.drop_column("streams", "effective_properties_json")
    op.drop_column("streams", "calculated_properties_json")
    op.drop_column("streams", "user_provided_properties_json")
    op.drop_column("streams", "stream_properties_json")
    op.drop_column("streams", "estimated")
    op.drop_column("streams", "tear_stream")
    op.drop_column("streams", "simulation_status")