"""P3.2 SIM-10.2：streams.is_mixed_phase 列（MIXED 相持久化标记）。

落地理由（用户 2026-09-09 提案）：
- PRO/II parser 遇 MIXED 相时，SIM-V01 BLOCK 需绕过（phase 置 None 避免 BLOCK）
- 但 MIXED 状态本身是数据事实：汽液混相，P4 composition 抽取需要回填
- 不引入 composition 抽取复杂性，先用 is_mixed_phase 持久化标记
- 下游 P 阶段可按 is_mixed_phase=True 精准筛选需特殊处理的流

字段语义：
- TRUE：PRO/II 原始相态为 MIXED（同时 phase 因绕过被置 None）
- FALSE/NULL：其他入口（手工/Excel 或 PRO/II 非 MIXED）

注：手工 / Excel 入口不传该字段（StreamBase 默认 None），行为等同 False。
    PRO/II parser 当前会显式传 False（非 MIXED 的 VAPOR/LIQUID 路径）。

Revision ID: p3sim_stream_is_mixed_phase
Revises: p3sim_stream_is_unreliable
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_stream_is_mixed_phase"
down_revision = "p3sim_stream_is_unreliable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """streams 加 is_mixed_phase 字段（P3.2 SIM-10.2 / 用户 2026-09-09 提案）。

    步骤：
    - is_mixed_phase Boolean NULL：未设置（默认 None 等价 False）

    字段语义：
    - TRUE：PRO/II 原始相态为 MIXED（同时 phase 因绕过被置 None）
    - FALSE/NULL：其他入口（手工/Excel 或 PRO/II 非 MIXED）

    业务：PRO/II parser 遇 MIXED 相时 SIM-V01 BLOCK 需绕过（phase 置 None 避免
    BLOCK），但 MIXED 状态本身是数据事实（汽液混相），P4 composition 抽取需
    回填；不引入 composition 抽取复杂性，先用 is_mixed_phase 持久化标记，下游
    P 阶段按 is_mixed_phase=True 精准筛选需特殊处理的流。手工/Excel 入口不传
    该字段（StreamBase 默认 None），行为等同 False；PRO/II parser 当前显式传
    False（非 MIXED 的 VAPOR/LIQUID 路径）。
    """
    op.add_column(
        "streams",
        sa.Column("is_mixed_phase", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """streams 删 is_mixed_phase 字段（P3.2 SIM-10.2 逆向）。

    步骤：
    - DROP COLUMN streams.is_mixed_phase

    业务：与 upgrade 互逆；MIXED 相持久化标记字段清理。
    """
    op.drop_column("streams", "is_mixed_phase")
