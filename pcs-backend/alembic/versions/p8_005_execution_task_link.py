"""P8c：执行日志补 `task_id` / `report_file_id`（b11 前后端时序契约）。

## 为什么需要这两列

b7 决策（2026-10-08 审查）：执行走 ARQ 异步，`POST /execute` 返回
**202 + `task_id`**，不出文件。文件由任务体渲染后写 `report_files`。

由此产生一个**之前没人发现的缺口**：

- `POST /execute` 只给 `task_id`
- `GET /report/{report_file_id}/status` **只认 `report_file_id`**
- 两者的映射**无处可查** —— `report_execution_logs` 两列都没有

后果：前端拿到 202 之后**永远拿不到文件**，执行面板转圈到超时。
这不是 UI 能绕过的实现细节，是契约缺一环。2026-10-13 用户裁决：
「如果第一批就发现问题……**修的是契约，不是 UI**」。

## 为什么不给 report_files 预建 PENDING 行

`report_service.store_rendered` 按**内容哈希** upsert（SPEC §2.5 同内容
复用同一行同一磁盘文件）。哈希要渲染完才知道，所以预建的 PENDING 行
与最终 upsert 出来的是**两行** —— 哈希去重语义直接失效，
「同内容重复生成复用同一个文件」这条（`test_same_content_twice_reuses_one_file`）
会从「复用」变成「重复落盘」。固定 10 类路径确实预建 PENDING 行
（`report_tasks._mark_pending`），但那条路径不走 `store_rendered`。

## 为什么两列都要

- `task_id`：轮询的**凭据**。同一个定义并发执行两次时，
  「该定义最近一次执行」会指错对象。
- `report_file_id`：执行**完成后**才回填。生成前是 NULL —— 这正是
  「还在跑」的信号，不需要额外的 status 列。

**幂等**：`ADD COLUMN IF NOT EXISTS`。**不**用 drop-then-create ——
`report_execution_logs` 有真实数据。
"""
from __future__ import annotations

from alembic import op

revision = "p8_005"
down_revision = "p8_004"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("task_id", "VARCHAR(64)"),
    ("report_file_id", "UUID"),
)


def upgrade() -> None:
    for name, sql_type in _NEW_COLUMNS:
        op.execute(
            f"ALTER TABLE report_execution_logs ADD COLUMN IF NOT EXISTS {name} {sql_type}")
    # 轮询按 task_id 查，必须有索引 —— 否则每次轮询都是全表扫，
    # 而轮询是每 2 秒一次、并发多个用户。
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_execution_logs_task_id "
        "ON report_execution_logs (task_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_execution_logs_task_id")
    for name, _t in reversed(_NEW_COLUMNS):
        op.execute(
            f"ALTER TABLE report_execution_logs DROP COLUMN IF EXISTS {name}")
