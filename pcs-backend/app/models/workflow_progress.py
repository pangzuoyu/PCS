"""workflow_progress ORM（ADR-0047 观测层 / SPEC P9A-OBS-001）。

记录签署 / 变更单 / 代录批准三类工作流的**节点实时进度**，供 P9B 的甘特图、
进度条与超时告警消费。

## 写入层纪律（ADR-0047 §① 🔒）

本表**只能**由 `app/services/workflow_progress_writer.record_step()` 写入，
且调用点**必须在 service 层**，不得写在 `app/api/v1/*` 路由处理函数里。

理由是实测的可达路径：`StateMachineService.transition()` 有 4 条入口，其中
`cia_engine.py:85`（`cia_mark_stale` 事件处理者）由 `app/workers/cia_tasks.py`
的 ARQ cron 驱动，**完全不经过 API 层**。写入放 API 层 ⇒ 所有 cron 驱动的
状态变更在观测层里系统性隐形，且不报错、不告警。

## 与 SPEC P9-OPEN-007「8 字段」的差异

SPEC 列 8 个字段，本表有 10 个业务列。多出的 `workflow_type` 与 `project_id`
是被 P9A 自己的需求强制的：前者是读 API 的 URL 段与三个写入点的区分依据
（ADR-0047 §①），后者是多态 `workflow_id` 无法 join 回项目时唯一的鉴权依据
（P9A-OBS-003 的越权 404）。差异登记在 `TODOS.md`，未回改 SPEC。

⚠️ **同名不同表**：`SUP-008 V1.1 §8.5` 的 `workflow_progress` 是另一张表 ——
14 字段的项目作业流程进度百分比表（Excel Sheet 2「作业流程」导入用）。
两者领域不同却共用表名，且 SPEC/ADR 引用的「SUP-008 §2.6」里**没有** 8 字段
定义（§2.6 实为「反应器计算」）。本表是 SPEC-P9 / ADR-0047 的观测表，不是那张。
详见 `.superpowers/sdd/PCS-PLAN-P9A-2-交付物写面/progress.md` 的 `Ruling P1`。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.mixins import TimestampMixin


class WorkflowProgress(TimestampMixin, Base):
    """工作流节点进度行（workflow_progress 表）。

    一行 = 某工作流的某个步骤在某个时刻的状态。同一
    (workflow_type, workflow_id, step_order) 只允许一行 —— 重复签署**更新**
    而非追加，否则甘特图会出现两个同序号步骤而读 API 分不出哪条是当前的。
    """

    __tablename__ = "workflow_progress"
    __table_args__ = (
        UniqueConstraint(
            "workflow_type",
            "workflow_id",
            "step_order",
            name="uq_workflow_progress_step",
        ),
    )

    progress_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflowtype", native_enum=True),
        nullable=False,
        index=True,
        comment="ADR-0047 §① 的 3 类工作流；新增第 4 类须先改 ADR",
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
        comment="多态：SIGN→deliverable_version_id / CHANGE_NOTICE→deliverable_id / "
        "CUSTOMER_APPROVAL_PROXY→deliverable_id",
    )
    step_order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="步骤序号；与 SignatureMatrix.steps_json.step_order 同义"
    )
    step_role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="步骤角色（SPEC 的 step_name）；SIGN / CUSTOMER_APPROVAL_PROXY 取 "
        "SignatureMatrix.steps_json.sign_role；CHANGE_NOTICE 取工作流类型本身"
        "（CHANGE_NOTICE 工作流只写 1 行，step_order=1）",
    )
    step_status: Mapped[WorkflowProgressState] = mapped_column(
        Enum(WorkflowProgressState, name="workflowprogressstate", native_enum=True),
        nullable=False,
        default=WorkflowProgressState.PENDING,
        comment="P9A-OBS-001 的 5 态",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="节点开始（IN_PROGRESS 时写）"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="节点终态时间；超时告警按它算"
    )
    assignee: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="该节点的负责人"
    )
    result_hash: Mapped[str | None] = mapped_column(
        String(64), comment="节点产出物的哈希（签署快照/审批结论），防篡改溯源"
    )
