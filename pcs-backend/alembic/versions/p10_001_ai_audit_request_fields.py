"""给 `ai_audit_log` 加 P10 的**请求审计** 8 列（P10-A · Task T7）。

## 为什么

SPEC §3.3.2「AI 审计日志：记录**所有** AI 请求响应」——
但仓里既有的 `ai_audit_log` 是 **SUP-006 强制**的「AI 决策与提示词审计」
（16 列，语义完全不同）⇒ 本迁移**给既有表加列**（偏离登记 D4），
**不动** SUP-006 的既有列与语义。

## ⚠️ 时间列**复用既有 `occurred_at`**（偏离登记 D16）

SPEC §4.1.4 的字段表里有 `timestamp` —— 但既有表**已经有** `occurred_at`
⇒ 再加一个 `timestamp` 就是**两个语义重叠的时间列** ⇒ 以后没人知道该读
哪个 ⇒ **复用 `occurred_at`，不新增时间列** ⇒ 本迁移加 **8** 列（不是 9）。

## ⚠️ 唯一索引**必须 partial**

既有 SUP-006 行的 `request_id` 为 NULL ⇒ PG 的唯一索引**允许多个 NULL**
—— 但只在索引是 partial（或列本身 NOT NULL）时才成立。这里用
`WHERE request_id IS NOT NULL` 显式声明 partial：
① 既有行不受约束；② 本批的 AI 请求审计行**必须**唯一（幂等写库的前提）。

## ⚠️ `op.create_index` 带 `if_not_exists=True`

`scripts/check_migration_idempotency.py` 的规则（`op.add_column` 不检查 ——
PG 不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`）。

## Revision

`revision = p10_001`，`down_revision = p9_015`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p10_001"
down_revision = "p9_015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加 8 列（全部 nullable）+ partial 唯一索引 + 查询索引."""
    op.add_column(
        "ai_audit_log",
        sa.Column("request_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("client_request_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("endpoint", sa.String(200), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("sanitized_request_hash", sa.String(80), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("response_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "ai_audit_log",
        sa.Column("model_version", sa.String(50), nullable=True),
    )
    # ⚠️ partial：既有 SUP-006 行的 request_id 为 NULL ⇒ 非 partial 会撞
    #    「重复 NULL」。
    op.create_index(
        "ux_ai_audit_log_request_id",
        "ai_audit_log",
        ["request_id"],
        unique=True,
        if_not_exists=True,
        postgresql_where=sa.text("request_id IS NOT NULL"),
    )
    # ⚠️ 复用既有 `occurred_at`（不新增时间列 · 偏离 D16）。
    op.create_index(
        "ix_ai_audit_log_endpoint_occurred_at",
        "ai_audit_log",
        ["endpoint", "occurred_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """反向：索引 → 列."""
    op.drop_index(
        "ix_ai_audit_log_endpoint_occurred_at", table_name="ai_audit_log", if_exists=True
    )
    op.drop_index(
        "ux_ai_audit_log_request_id", table_name="ai_audit_log", if_exists=True
    )
    op.drop_column("ai_audit_log", "model_version")
    op.drop_column("ai_audit_log", "response_summary")
    op.drop_column("ai_audit_log", "sanitized_request_hash")
    op.drop_column("ai_audit_log", "duration_ms")
    op.drop_column("ai_audit_log", "status_code")
    op.drop_column("ai_audit_log", "endpoint")
    op.drop_column("ai_audit_log", "client_request_id")
    op.drop_column("ai_audit_log", "request_id")
