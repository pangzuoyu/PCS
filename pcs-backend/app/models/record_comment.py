"""record_comments ORM（P9A B4c）。

⚠️ **这张表是本轮新建的，计划里没有**：SPEC §2.2.3 列了
`POST /records/{module}/{id}/comments`，但全仓 `grep "class Comment"` 零命中。
不建表就只能返回「假批注」（响应成功、刷新即消失）—— 那比没有这个端点更坏：
用户以为意见记下来了。

## 为什么带 `record_type` + `record_id` 两个列而不是一个外键

记录是多态的（16+ 张结果表，见 `calc_lineage.RECORD_TYPE_REGISTRY`），
没有一张能当它的父表。存 `(record_type, record_id)` 组合键是本仓的既有形状
（`deliverable_record_bindings` / `record_change_snapshots` 都是这么做的）。

代价是**没有外键保护**：批注可以指向一条已被删掉的记录。缓解办法是
读端点仍先解析记录（不存在 → 404），所以孤儿批注读不到，只是占着地方。

## 批注不是观测

ADR-0047 §① 明写「不写『打开页面』『查看』等读行为」—— 批注**不写**
`workflow_progress`。把「有人留言」算成工作流活动会让甘特图上的活动看起来
比实际多，而观测层一旦不可信就没人再信它。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class RecordComment(TimestampMixin, Base):
    """记录批注（record_comments 表）。"""

    __tablename__ = "record_comments"
    __table_args__ = (
        # 读路径固定为「按记录取、按时间正序翻页」。索引把它做成
        # (record_type, record_id) 前缀 ⇒ 翻页是范围扫描而非全表扫。
        #
        # ⚠️ 必须带 comment_id 作为 tiebreaker：`created_at` 是
        # `server_default=func.now()`，SQLite 下 CURRENT_TIMESTAMP 只有秒级粒度
        # ⇒ 同一批写入的批注时间戳必然相同，只按 created_at 排序时并列行的
        # 返回顺序不确定，翻页会漏批注或重复（与 deliverable_service 同源问题）。
        Index(
            "ix_record_comments_record_created",
            "record_type",
            "record_id",
            "created_at",
            "comment_id",
        ),
    )

    comment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    record_type: Mapped[str] = mapped_column(
        String(30), comment="calc_lineage.RECORD_TYPE_REGISTRY 的键，如 PipingResult"
    )
    record_id: Mapped[uuid.UUID] = mapped_column(comment="多态记录主键")
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, comment="留言人")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
