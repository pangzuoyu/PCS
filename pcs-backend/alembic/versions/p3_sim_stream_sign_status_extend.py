"""P3.2 SIM-13：streamsignstatus PG enum 扩展为 9 态（用户裁决 P0 闭环 D-1）。

落地理由：
- P1 StateMachineService.transition()（app/services/state_machine.py）
  13 事件流转到 RecordSignStatus9 全 9 态（DRAFT/IN_APPROVAL/CHECKED/
  CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）
- 原 PG enum streamsignstatus 仅 4 态（DRAFT/IN_APPROVAL/CHECKED/OBSOLETE），
  缺 CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING
- SIM-13 6 端点用到 4 个新值：CHECK_REJECTED / STALE / CHANGE_PENDING / CHANGED
  （REVERSAL_PENDING 留给 P3.3 撤销流，本次一并加齐）
- PG 12+ 允许 ALTER TYPE ADD VALUE 在事务内执行（值不在同事务引用前提下）

不可逆警告（cerebrum 2026-09-08 锁定）：
- PG enum ADD VALUE 不可 DROP VALUE
- 本迁移扩展是单向操作；如需回退，必须 ALTER TABLE ... TYPE varchar(20)
  重建枚举

Revision ID: p3sim_stream_sign_status_extend
Revises: p3sim_stream_state_machine_fields
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_stream_sign_status_extend"
down_revision = "p3sim_stream_state_machine_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS：保证幂等（重复 apply 不报错）
    op.execute("ALTER TYPE streamsignstatus ADD VALUE IF NOT EXISTS 'CHECK_REJECTED'")
    op.execute("ALTER TYPE streamsignstatus ADD VALUE IF NOT EXISTS 'STALE'")
    op.execute("ALTER TYPE streamsignstatus ADD VALUE IF NOT EXISTS 'CHANGE_PENDING'")
    op.execute("ALTER TYPE streamsignstatus ADD VALUE IF NOT EXISTS 'CHANGED'")
    op.execute("ALTER TYPE streamsignstatus ADD VALUE IF NOT EXISTS 'REVERSAL_PENDING'")


def downgrade() -> None:
    # PG enum 不可 DROP VALUE；降级文档：手动重建 enum 或 ALTER TABLE ... TYPE varchar
    # 此处仅抛 NotImplementedError，提示用户决策
    raise NotImplementedError(
        "PG enum streamsignstatus ADD VALUE 不可逆；"
        "如需回退需手动 ALTER TABLE streams ALTER COLUMN sign_status "
        "TYPE varchar(20) USING sign_status::varchar(20); "
        "DROP TYPE streamsignstatus;"
    )
