"""notifications ORM（ADR-0049 §① 通知建表）。

通知是**发生过的事实**：「你被退回过」在记录已改正后依然成立，
而实时计算会返回空 —— 这是它与待办（§② 实时计算）形态不同的根本原因，
也是本表存在的理由。

## 为什么没有 `project_id`

对比 `record_comments` / `workflow_progress`（都有 `project_id`）。
通知的读路径是「当前用户读自己的」，鉴权身份**就是** `recipient_id` 本身。
多一列 `project_id` 会让它变成第二个可被写错、且写错后鉴权仍然通过的依据 ——
越权读别人项目的通知，而没有任何一处会报错。
`PUT /notifications/{id}/read` 同样按 `recipient_id` 判归属。

## `kind` 是 String(40) 不是 PG enum

ADR-0049 §① 的 DTO 声明的是 `kind: str`。若 DB 侧再开一个 PG enum，
「Python 侧有哪些 kind」与「DB 允许哪些 kind」就成了两份必须同步维护的清单 ——
本仓已经为 `RECORD_TYPE_REGISTRY` 的同类问题付过代价（TODO-058 裁决：
注册表是表枚举，能力是从 `RecordMixin` 推导的谓词，**不给同一件事建两份人工清单**）。
⇒ 单一来源是 `NotificationKind`，DB 列放宽为 String，新增 kind 不需要迁移。

## 写侧纪律

本表**只能**由 `app/services/notifications/in_app.py` 的
`InAppChannel.deliver()` 写入。触发点可以有多个，写入点只有一个 ——
多写入点意味着将来有人绕过通道抽象直接插行，而那正是 ADR-0049 §①
明令禁止的「临时 if」。

WebSocket 推送**不由本表负责**，也不在通道里做（ADR-0049 §①：
通道不应该知道 WebSocket 存在）。推送由写侧在 `deliver()` 成功后
另行通知 broadcaster。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class NotificationKind(StrEnum):
    """通知种类 —— 本仓**唯一**的 kind 清单。

    四个成员对应用户 2026-10-20 裁决的最小接线集合。
    新增触发源前先回 ADR-0049 补记：这张表是裁决过的边界，
    「顺手再加一个」会让通知流退化成无人设计的杂烩。
    """

    SIGN_COMPLETED = "SIGN_COMPLETED"
    STEP_RETURNED = "STEP_RETURNED"
    PROXY_RECORDED = "PROXY_RECORDED"
    CHANGE_NOTICE_APPROVED = "CHANGE_NOTICE_APPROVED"


class Notification(TimestampMixin, Base):
    """站内通知（notifications 表）。"""

    __tablename__ = "notifications"
    __table_args__ = (
        # ADR-0049 §③：未读**计数**（铃铛红点）靠它。建成全量索引时已读行
        # 也进索引，未读占比一降索引就失去选择性 ⇒ 必须是 partial index。
        #
        # ⚠️ **它不是 500ms 指标的全部支撑**（2026-10-20 真库实测修正）：
        # 断线兜底**列表**带 `ORDER BY created_at DESC`，而本索引没有
        # created_at ⇒ **排不了序** ⇒ planner 选的是
        # `ix_notifications_recipient_created`。两个索引各有各的用处。
        Index(
            "ix_notifications_recipient_unread",
            "recipient_id",
            "read_at",
            postgresql_where=text("read_at IS NULL"),
        ),
        # 断线兜底（ADR-0049 §⑤ 约束 1）：`GET /notifications?after=<last_seen>`
        # 按 created_at 范围翻页，没有这个索引就是全表扫。
        Index(
            "ix_notifications_recipient_created",
            "recipient_id",
            "created_at",
        ),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id"),
        comment="收件人；两个复合索引都以它打头 ⇒ 不另建单列索引",
    )
    kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="NotificationKind 枚举之一；本仓唯一清单在 app/models/notification.py。"
        "无读路径按 kind 过滤 ⇒ 不建索引",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="铃铛上的一行标题")
    body: Mapped[str] = mapped_column(Text, nullable=False, comment="通知正文")
    detail_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="结构化上下文（P9A-DLV-010：字段级摘要走 NotificationDetail schema，"
        "不是自由 dict）",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="已读时刻；NULL = 未读"
    )
