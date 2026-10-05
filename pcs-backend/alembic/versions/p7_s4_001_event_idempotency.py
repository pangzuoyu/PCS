"""p7_s4_001: event_idempotency 表（事件幂等凭据 / D4 裁决 4A 落地前置）.

P7 Sprint 4 Task S4-0。事件去重的唯一权威凭据 —— 同一 `event_id` 重复投递时
listener 一次都不再被调用。

为什么不用 audit_logs（见 `docs/PCS-NOTE-CIA-反向恢复-推到P8-2026-10-05.md`）:
  - 去重是**业务正确性**要求, 不能因进程重启而失效（内存态做不到）
  - audit_logs 是只增不改的审计流, 且有保留期清理（D8 monthly partition
    保留 6 月）→ 清理后重复事件会被重新执行

`before_json` 存覆盖前快照（P8 反向恢复来源）: 值一旦被覆盖就永久丢失,
故必须随事件持久化。`audit_logs.detail_json` 只记 event_id 引用与摘要。

Revision ID: p7_s4_001
Revises: p7_s3_005
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s4_001"
down_revision = "p7_s3_005"
branch_labels = None
depends_on = None

_TABLE = "event_idempotency"


def upgrade() -> None:
    """建 event_idempotency 表 (event_id 主键 → 天然去重)."""
    op.create_table(
        _TABLE,
        # 主键即去重闸: 同 event_id 第二次 INSERT 撞 PK
        sa.Column("event_id", sa.Uuid(), primary_key=True,
                  comment="事件 ID (反向事件复用原 id → 天然幂等)"),
        sa.Column("event_type", sa.String(64), nullable=False,
                  comment="事件类型"),
        sa.Column("payload_hash", sa.String(64), nullable=False,
                  comment="payload 指纹; 同 id 不同 hash → EVENT_ID_CONFLICT"),
        sa.Column("before_json", postgresql.JSONB(),
                  comment="覆盖前快照 (P8 反向恢复来源; deepcopy 后存储, 只读)"),
        sa.Column("processed_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False,
                  comment="处理时间"),
    )
    op.create_index(
        "ix_event_idempotency_event_type", _TABLE, ["event_type"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """删 event_idempotency 表 (if_exists 幂等)."""
    op.drop_table(_TABLE)
