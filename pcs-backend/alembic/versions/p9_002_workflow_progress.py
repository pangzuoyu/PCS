"""P9A 观测层迁移：workflow_progress 表 + 2 个 PG enum（ADR-0047 观测层）。

SPEC P9A-OBS-001（8 字段 + 5 态枚举）/ ADR-0047（同步写 + 写入点在 service 层）。

## 业务字段是 10 个而不是 SPEC 列的 8 个

SPEC P9-OPEN-007 列 8 个（`workflow_id / step_no / step_name / step_status /
started_at / completed_at / assignee / result_hash`），本迁移建 10 个业务列。
多出的两列是被 P9A 自己的需求强制的，不是设计口味：

- `workflow_type` —— 读 API 的 URL 段是 `{workflow_type}/{workflow_id}`
  （P9A-OBS-003），且 ADR-0047 §① 的三个写入点靠它区分。缺了它，一次签署与
  一次代录的进度行无法分辨，甘特图会把两条工作流画成一条。
- `project_id` —— 读 API 要按项目鉴权（越权 404），而 `workflow_id` 是多态的
  （版本 ID / 交付物 ID），无法 join 回项目。

差异登记在 `TODOS.md`。**不回改 SPEC** —— SPEC 是绑定权威，改它要重走 §7.2 验收。

## 列名与 SPEC 的两处改名

`step_no` → `step_order`、`step_name` → `step_role`，为与
`SignatureMatrix.steps_json` 的键（`step_order` / `sign_role`）逐字一致 ——
写入时无需翻译层，多一个要同步维护的映射就多一个能漂移的地方。

## ⚠️ 同名不同表

`SUP-008 V1.1 §8.5` 也叫 `workflow_progress`，但那是 14 字段的**项目作业流程
进度百分比表**（Excel Sheet 2「作业流程」导入用），与本表的观测语义无关。
本迁移**不是**那张表，将来若要建它需另议表名。
详见 `.superpowers/sdd/PCS-PLAN-P9A-2-交付物写面/progress.md` 的 `Ruling P1`。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p9_002"
down_revision = "p9_001"
branch_labels = None
depends_on = None

workflowtype_enum = postgresql.ENUM(
    "SIGN",
    "CHANGE_NOTICE",
    "CUSTOMER_APPROVAL_PROXY",
    name="workflowtype",
    create_type=False,
)

workflowprogressstate_enum = postgresql.ENUM(
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "SKIPPED",
    "FAILED",
    name="workflowprogressstate",
    create_type=False,
)


def upgrade() -> None:
    # create_type=False 于上、True 于下：PG 里类型在 create_table 之前就要存在，
    # 但 downgrade 必须显式回收 —— 否则类型泄漏，`alembic downgrade base` 后
    # 再 upgrade 会撞「type already exists」。
    bind = op.get_bind()
    workflowtype_enum.create(bind, checkfirst=True)
    workflowprogressstate_enum.create(bind, checkfirst=True)

    op.create_table(
        "workflow_progress",
        # ⚠️ 与 ORM 声明逐字一致（app/models/workflow_progress.py）——
        # 不一致时 `alembic check` 报漂移，而漂移是**绿灯看不见**的那一类
        # （CLAUDE.md 漂移盲区：缺表会红，漂移会绿）。
        sa.Column("progress_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_type", workflowtype_enum, nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_role", sa.String(length=30), nullable=False),
        sa.Column("step_status", workflowprogressstate_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee", sa.Uuid(), nullable=True),
        sa.Column("result_hash", sa.String(length=64), nullable=True),
        # TimestampMixin 三列（app/models/mixins.py:34-41）
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"]),
        sa.PrimaryKeyConstraint("progress_id"),
        # 同一工作流同一顺序号只允许一行：重复签署更新而非追加，
        # 否则甘特图出现两个同序号步骤，而读 API 分不出哪条是当前的。
        sa.UniqueConstraint(
            "workflow_type",
            "workflow_id",
            "step_order",
            name="uq_workflow_progress_step",
        ),
    )
    # 读 API（P9A-OBS-003）按 (workflow_type, workflow_id) 查；无索引则每次全表扫。
    op.create_index(
        "ix_workflow_progress_project_id",
        "workflow_progress",
        ["project_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_workflow_progress_workflow_type",
        "workflow_progress",
        ["workflow_type"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_workflow_progress_workflow_id",
        "workflow_progress",
        ["workflow_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_progress_workflow_id",
        table_name="workflow_progress",
        if_exists=True,
    )
    op.drop_index(
        "ix_workflow_progress_workflow_type",
        table_name="workflow_progress",
        if_exists=True,
    )
    op.drop_index(
        "ix_workflow_progress_project_id",
        table_name="workflow_progress",
        if_exists=True,
    )
    op.drop_table("workflow_progress", if_exists=True)

    bind = op.get_bind()
    workflowprogressstate_enum.drop(bind, checkfirst=True)
    workflowtype_enum.drop(bind, checkfirst=True)
