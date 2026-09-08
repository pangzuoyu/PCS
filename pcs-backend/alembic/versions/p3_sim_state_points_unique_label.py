"""P3.2 SIM-10：stream_state_points (stream_id, case_type, state_label) 唯一约束。

闭环 bug-062：SV05 仅 intra-batch 查重（seen_keys 集合），跨批次 duplicate 漏掉。
DB 层 UniqueConstraint 提供最后兜底，commit 时 SQLAlchemy IntegrityError 由
StreamService.create_state_point 拦截后转 PcsError(SIM_STATEPOINT_BLOCKED)。

约束字段：stream_id (FK 隐含 project_id) + case_type (4 态) + state_label。
  - 不同 stream：约束不冲突
  - 同 stream 不同 case_type：允许（NORMAL/MAX/MIN/ALTERNATE 并存）
  - 同 stream + 同 case_type + 同 state_label：拒绝

Revision ID: p3sim_state_points_unique_label
Revises: p3sim_stream_upgrade
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_state_points_unique_label"
down_revision = "p3sim_stream_upgrade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_stream_state_points_label",
        "stream_state_points",
        ["stream_id", "case_type", "state_label"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_stream_state_points_label", "stream_state_points", type_="unique"
    )