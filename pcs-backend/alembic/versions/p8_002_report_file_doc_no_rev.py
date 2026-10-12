"""P8: report_files 加 doc_no / rev.

verify 端点（Task 8）的响应含 `{match, doc_no, rev, generated_at}` ——
现场扫码的人靠 doc_no / rev 确认自己扫的是哪一份。

**幂等**：`ADD COLUMN IF NOT EXISTS`，可重复执行。
⚠️ **不套用 p8_001 的 drop-then-create** —— 那 4 张表是新建或 0 行空壳，
本表会有真实数据，drop 一次就是一次全表删除。
"""
from __future__ import annotations

from alembic import op

revision = "p8_002"
down_revision = "p8_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加两列。幂等: ADD COLUMN IF NOT EXISTS."""
    op.execute("ALTER TABLE report_files ADD COLUMN IF NOT EXISTS doc_no VARCHAR(50)")
    op.execute("ALTER TABLE report_files ADD COLUMN IF NOT EXISTS rev VARCHAR(20)")


def downgrade() -> None:
    """删两列。幂等: DROP COLUMN IF EXISTS."""
    op.execute("ALTER TABLE report_files DROP COLUMN IF EXISTS rev")
    op.execute("ALTER TABLE report_files DROP COLUMN IF EXISTS doc_no")