"""P8：report_execution_logs 补 `status` 列（TODO-064 的回收器需要它）。

## 为什么不能靠 `report_file_id IS NULL` 表达「失败」

轮询端点此前是**合成**状态的：`report_file_id` 有值 → FINISHED，
否则 → RUNNING。于是「已入队」「正在跑」「已经僵死」三种情况长得一模一样，
回收器没有地方写下第三种 —— 它只能删行，而这是一张**审计**表，删了就查不到
「谁在什么时候请求过这次执行」。

## 为什么不用 `reclaimed_at` 之类的附加列

那会让状态有两个来源（`report_file_id` 与 `reclaimed_at`），端点要同时读
两个列去推断。相比之下 `status` 是**唯一真相**，端点直接读。

## 回填

加列时既有行必须一并定状态，否则升级完老行会一律显示 QUEUED ——
包括那些其实早就生成成功、`report_file_id` 有值的行。
"""
from __future__ import annotations

from alembic import op

revision = "p8_007"
down_revision = "p8_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE report_execution_logs "
        "ADD COLUMN IF NOT EXISTS status VARCHAR(16)")
    # ⚠️ 回填不能省：默认 QUEUED 会把**已经成功**的老行也标成排队中。
    # 升级后老行仍在库里（审计表没人删过），端点一读就是错的。
    op.execute(
        "UPDATE report_execution_logs SET status = "
        "CASE WHEN report_file_id IS NOT NULL THEN 'FINISHED' ELSE 'QUEUED' END "
        "WHERE status IS NULL")
    # ⚠️ **必须与 ORM 声明逐字一致**（`nullable=False, server_default="QUEUED"`）。
    # 少写这两句的后果不是报错，是 `alembic check` 报漂移 ——
    # 而 CLAUDE.md 记着：漂移是**绿灯看不见**的那一类（缺表会红，漂移会绿）。
    #
    # 这两句要写成无条件 ALTER：ADD COLUMN IF NOT EXISTS 在「列已存在」时是
    # 空操作，于是**已经跑过旧版这条迁移的库**（开发库就是）拿不到约束。
    # 幂等地重复执行 ALTER 才是安全的。
    op.execute(
        "ALTER TABLE report_execution_logs ALTER COLUMN status SET DEFAULT 'QUEUED'")
    op.execute(
        "ALTER TABLE report_execution_logs ALTER COLUMN status SET NOT NULL")
    # 回收器按 status 扫描；没索引就是每次 cron 一次全表扫。
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_execution_logs_status "
        "ON report_execution_logs (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_execution_logs_status")
    op.execute("ALTER TABLE report_execution_logs DROP COLUMN IF EXISTS status")