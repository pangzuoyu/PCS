"""p10_004：pms_items 表（P10-H · T2 · TODO-195）。

## 为什么

前端 P45-3-8 Task 35 画了「PMS 管道材料规格」页 ⇒ ⇒ 但**后端从来没有这个
实体** ⇒ ⇒ `/pms` 页只能占位（TODO-159 / TODO-195）。
人裁（2026-11-23）：「沿用前端形状 + 签署流」⇒ ⇒ 建项目级表。

## 表形状

`RecordMixin` 全套（tag_number / sign_status / record_hash / approval_* /
change_* / obsoleted_* / reversal_* / 审计三列 / project_id / workspace_id）
+ 4 个业务列（pms_no / description / pms_class / hazard_level）。

⇒ ⇒ 继承 `RecordMixin` ⇒ ⇒ **9 态工作流**直接可用
（`/records/PmsItem/{id}/submit-approval` 等）⇒ ⇒ 不另造签署框架。

⚠️ **tag_number 可空**：PMS 用 `RecordMixin`（不是 `TaggedRecordMixin`）
⇒ ⇒ 位号不是它的业务键（业务键是 `pms_no`）。

## 约束

- `uq_pms_items_project_pms_no` —— PMS 编号**项目内**唯一。
- `ck_pms_items_hazard_level` —— 危险等级三值（LOW / MEDIUM / HIGH）。
  ⚠️ 与 `app/schemas/pms.py::HazardLevel`（Literal）**同一份口径**
  ⇒ ⇒ Python 侧改枚举 ⇒ ⇒ 这里必须同步（`alembic check` 抓不到 CHECK 漂移
  ⇒ ⇒ 靠 `tests/` 里的守卫）。

## 幂等

`create_table` / `create_index` 都带 `if_not_exists` ⇒ ⇒ 重复跑不炸。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p10_004"
down_revision = "p10_003"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())

# recordsignstatus enum 复用（P3.2 SIM-13 已创建；create_type=False 复用）
_recordsignstatus_enum = postgresql.ENUM(
    "DRAFT", "IN_APPROVAL", "CHECKED", "CHECK_REJECTED", "STALE",
    "CHANGE_PENDING", "CHANGED", "REVERSAL_PENDING", "OBSOLETE",
    name="recordsignstatus",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "pms_items",
        sa.Column("item_id", sa.Uuid(), nullable=False),
        # === 业务列 ===
        sa.Column(
            "pms_no", sa.String(length=40), nullable=False,
            comment="PMS 编号（项目内唯一）",
        ),
        sa.Column("description", sa.String(length=300), nullable=False, comment="描述"),
        sa.Column(
            "pms_class", sa.String(length=40), nullable=False,
            comment="材料等级 / 类别",
        ),
        sa.Column(
            "hazard_level", sa.String(length=10), nullable=False,
            comment="危险等级 LOW / MEDIUM / HIGH（驱动审批层级）",
        ),
        # === RecordMixin ===
        sa.Column(
            "tag_number", sa.String(length=50), nullable=True,
            comment="位号/管道号（PMS 不用它做业务键）",
        ),
        sa.Column(
            "sign_status", _recordsignstatus_enum, nullable=False,
            server_default=sa.text("'DRAFT'::recordsignstatus"),
            comment="记录门禁 9 态（SUP-007 §3.1）",
        ),
        sa.Column(
            "record_hash", sa.String(length=64), nullable=False,
            comment="SHA-256，数值规范化舍入 6 位有效数字；未计算时空串",
        ),
        sa.Column("approval_step", sa.Integer(), nullable=True,
                  comment="IN_APPROVAL 当前步骤(1-based)"),
        sa.Column("approval_depth", sa.Integer(), nullable=False,
                  comment="该记录类型批准深度快照(1-4)"),
        sa.Column("approval_role", sa.String(length=30), nullable=True,
                  comment="当前待批角色 ApprovalRole"),
        sa.Column(
            "approval_chain_snapshot", JSONB, nullable=True,
            comment="提交送审时冻结的批准链",
        ),
        sa.Column("locked_by_deliverable", sa.Boolean(), nullable=False,
                  comment="被交付物快照绑定即锁定"),
        sa.Column("change_pending_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_resolved_by", sa.String(length=64), nullable=True),
        sa.Column("change_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_abandoned_reason", sa.String(length=500), nullable=True),
        sa.Column("obsoleted_reason", sa.String(length=200), nullable=True),
        sa.Column("obsoleted_by", sa.Uuid(), nullable=True),
        sa.Column("obsoleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("obsoleted_via_deliverable_id", sa.Uuid(), nullable=True,
                  comment="已绑定记录经 RECORD_CANCELLATION 变更单弃用"),
        sa.Column("reversal_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_requested_by", sa.Uuid(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.Column("reversal_approved_by", sa.Uuid(), nullable=True),
        sa.Column("reversal_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_resolution_path", sa.String(length=30), nullable=True,
                  comment="STALE 后走的重算路径"),
        sa.Column("hash_changed", sa.Boolean(), nullable=True,
                  server_default=sa.text("FALSE"),
                  comment="record_hash 相对上版是否实质变化"),
        sa.Column("changed_fields", JSONB, nullable=True,
                  comment="实质变化字段清单"),
        # === declared_attr FK 列 ===
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        # === TimestampMixin ===
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"],
            name="fk_pms_items_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.workspace_id"],
            name="fk_pms_items_workspace_id_workspaces",
        ),
        sa.PrimaryKeyConstraint("item_id", name="pk_pms_items"),
        sa.UniqueConstraint(
            "project_id", "pms_no", name="uq_pms_items_project_pms_no"
        ),
        sa.CheckConstraint(
            "hazard_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_pms_items_hazard_level",
        ),
    )
    # mixin 的 index=True ⇒ ⇒ 三条 ix
    op.create_index("ix_pms_items_project_id", "pms_items", ["project_id"],
                    if_not_exists=True)
    op.create_index("ix_pms_items_workspace_id", "pms_items", ["workspace_id"],
                    if_not_exists=True)
    op.create_index("ix_pms_items_sign_status", "pms_items", ["sign_status"],
                    if_not_exists=True)
    op.create_index("ix_pms_items_created_at", "pms_items", ["created_at"],
                    if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_pms_items_created_at", table_name="pms_items", if_exists=True)
    op.drop_index("ix_pms_items_sign_status", table_name="pms_items", if_exists=True)
    op.drop_index("ix_pms_items_workspace_id", table_name="pms_items", if_exists=True)
    op.drop_index("ix_pms_items_project_id", table_name="pms_items", if_exists=True)
    op.drop_table("pms_items", if_exists=True)
