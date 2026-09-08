"""P3.2 SIM-13：streams 状态机字段补齐（用户裁决 P0 闭环 D-1）。

落地理由：
- P1 StateMachineService.transition()（app/services/state_machine.py）
  对 13 种事件 setattr 以下字段：
  * change_pending_since  (MARK_STALE / INITIATE_CHANGE)
  * change_resolved_at    (APPLY_CHANGE)
  * change_resolved_by    (APPLY_CHANGE, str(actor_user_id))
- Stream ORM 当前缺这三个字段，调用 StateMachineService 会在
  setattr 阶段抛 AttributeError。
- 本迁移补齐，仅落地 SIM-13 6 端点真正用到的字段：
  submit/approve/reject 不需，initiate_change + mark_stale 用
  change_pending_since，pass_change 用 change_resolved_at/by。

未落地字段（YAGNI，SIM-13 范围外）：
- change_abandoned_at / reason（ABANDON_CHANGE，P3.3+ 撤销流用）
- reversal_* 字段（REQUEST/APPROVE/REJECT_REVERSAL，P3.4+ 撤销链路）
- obsoleted_at / by / reason（OBSOLETE，P3.4+ 退役用）

Revision ID: p3sim_stream_state_machine_fields
Revises: p3sim_stream_is_mixed_phase
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_stream_state_machine_fields"
down_revision = "p3sim_stream_is_mixed_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "streams",
        sa.Column(
            "change_pending_since",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="INITIATE_CHANGE / MARK_STALE 触发时间",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "change_resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="APPLY_CHANGE 完成时间（pass_change 闭环）",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "change_resolved_by",
            sa.String(64),
            nullable=True,
            comment="APPLY_CHANGE 审批人 ID（str(uuid) 形式，state_machine 用）",
        ),
    )


def downgrade() -> None:
    op.drop_column("streams", "change_resolved_by")
    op.drop_column("streams", "change_resolved_at")
    op.drop_column("streams", "change_pending_since")
