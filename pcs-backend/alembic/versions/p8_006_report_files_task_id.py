"""P8：report_files 补 `task_id`（固定 10 类报表的 202 → 文件桥）。

SPEC P8 §a7 要求「任务提交 → 轮询状态 → 完成/失败」，而
`POST /report/generate` 此前只回 `task_id`，`/report/{id}/status` 只认
`report_file_id` —— **两者之间没有任何桥**，调用方拿不到文件 id
（TODO-063）。

## 为什么不复用 report_execution_logs 那套

那张表的 `def_id` 是 **NOT NULL 外键**指向 `report_definitions`，而固定 10 类
报表**没有** report_definition —— 复用它就得让 `def_id` 可空再加一列
`report_type`，等于给一张审计表加一个恒为空的语义分支。

而 `report_files` 本来就是这次执行的产物行，状态、文件路径、字节数都在它
身上。加一列 `task_id` 就够了。

## 为什么不是「worker 跑起来再建行」

因为那样 202 与「行存在」之间有窗口，轮询端点在窗口里只能 404
（report-builder 那条路已经踩过这个坑，见 bug-167）。所以行由**端点在入队
时**建，worker 反过来按 `task_id` 复用它。
"""
from __future__ import annotations

from alembic import op

revision = "p8_006"
down_revision = "p8_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE report_files ADD COLUMN IF NOT EXISTS task_id VARCHAR(64)")
    # 重试复用同一行：worker 按 task_id 找自己那一行。ARQ 重试时
    # `_job_id` 不变，所以这个索引同时是「重试不产生第二行」的保证。
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_files_task_id "
        "ON report_files (task_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_files_task_id")
    op.execute("ALTER TABLE report_files DROP COLUMN IF EXISTS task_id")