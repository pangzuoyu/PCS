"""P3.2 SIM-10.1：streams.is_unreliable 列（用户 2026-09-09 裁决）。

落地理由：
- 下游过滤刚需（SIM-11 E2E + 后续 P 阶段下游计算模块需稳定识别 unreliable）
- unreliable=True 是物流本身状态，不是导入会话临时属性
- 同一 stream 可能多次导入，每次 convergence 不同，需要持久化字段

字段语义：
- NULL：未设置（等价 False，多用于手工/Excel 入口默认）
- TRUE：PRO/II NOT_CONVERGED/ABORTED 单元产品 → unreliable
- FALSE：PRO/II CONVERGED/WARNINGS 流显式标 False

注：手工 / Excel 入口不传该字段（StreamBase 默认 None），行为等同 False。

Revision ID: p3sim_stream_is_unreliable
Revises: p3sim_state_points_unique_label
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_stream_is_unreliable"
down_revision = "p3sim_state_points_unique_label"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "streams",
        sa.Column("is_unreliable", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("streams", "is_unreliable")