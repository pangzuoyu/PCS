"""P8 报表与输出 ORM（ADR-P8-001 全直接生成路线）。

4 张表：
- `report_styles`          样式配置（ReportStyle 的 JSON 快照）
- `report_files`           生成文件元数据（按内容哈希命名）
- `report_definitions`     自定义报表定义（REPORT_BUILDER）
- `report_execution_logs`  执行审计

**不含** .dotx / .xltx 模板表 —— ADR-P8-001 已废止用户提供模板的机制，
样式改由 `ReportStyle` JSON 驱动。

`report_definitions` / `report_execution_logs` 沿用 bootstrap 迁移
`dd47298c9c38` 起的表名，但那两张表**从未被使用**（无 service / API / 前端
引用，0 行），字段与 SPEC-P8 §3.2.2(2) 完全不同。用户 2026-10-08 裁决就地改造，
避免仓库里同时存在两个「报表定义」概念。
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ReportStyleRow(TimestampMixin, Base):
    """报表样式配置（report_styles 表）。

    `style_json` 是 `ReportStyle` 的序列化结果；`style_version` 随报表生成记录
    冻结，保证可复现（ADR-P8-001 §样式配置的存储）。
    """

    __tablename__ = "report_styles"
    __table_args__ = (
        UniqueConstraint("report_type", "project_id", "version",
                         name="uq_report_styles_scope_version"),
        Index("ix_report_styles_report_type", "report_type"),
    )

    style_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # nullable=True：公司级样式不属于任何项目
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    style_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class ReportFile(TimestampMixin, Base):
    """生成文件元数据（report_files 表）。

    文件按**内容哈希**命名，同内容重复生成复用同一行 —— 对应 SPEC §2.5
    「文件不可变性」与 Review Focus #5。

    ⚠️ **`project_id` 刻意不加 FK**（与 ReportStyleRow / ReportDefinition 不同）。
    加了 `ondelete=CASCADE` 的话，项目一删 DB 行没了但磁盘文件还在 → 变成无
    记录的孤儿文件，比有记录更难排查。不加 FK 则这些行仍在，可被清理任务
    （ADR-P8-004 待确认）按条件捞出。**不要「顺手补上 FK」。**
    """

    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_report_files_content_hash"),
        Index("ix_report_files_project_id", "project_id"),
        Index("ix_report_files_status", "status"),
    )

    report_file_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 刻意无 FK，见上方 docstring
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 生成时冻结的样式版本，保证可复现
    style_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 异步任务状态：PENDING / SUCCEEDED / FAILED
    status: Mapped[str] = mapped_column(String(20), default="SUCCEEDED", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 任务心跳。ARQ 进程被 kill 时状态会永远卡在 PENDING，Task 7 的回收任务
    # 靠这个字段识别僵死任务 —— 没有它前端会无限轮询且无人知道。
    heartbeat_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False,
    )
    # 是否含假设数据声明页（SPEC §3.2.1(4)）
    has_assumption_page: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ReportDefinition(TimestampMixin, Base):
    """自定义报表定义（report_definitions 表，REPORT_BUILDER）。

    `definition_json` 承载 SPEC §3.2.2(2) 的 DataSources / SelectedFields /
    FilterConditions / SortBy。**JOIN 只能取 datasource_registry 白名单**，
    不接受任意关联键（SPEC §1.3）。
    """

    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_report_definitions_project_name"),
        Index("ix_report_definitions_status", "status"),
    )

    def_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 设备类/管道类/物流类/综合类/管理类
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    # 全部用户/指定角色/仅创建人
    shared_with: Mapped[str] = mapped_column(String(20), default="CREATOR_ONLY", nullable=False)


class ReportExecutionLog(TimestampMixin, Base):
    """执行审计（report_execution_logs 表）。

    `condition_snapshot` 必存 —— 执行时允许临时调整过滤条件而不改定义本身，
    事后要能复现当时查了什么（SPEC §3.2.2(5)）。
    """

    __tablename__ = "report_execution_logs"
    __table_args__ = (Index("ix_report_execution_logs_def_id", "def_id"),)

    log_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    def_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("report_definitions.def_id", ondelete="CASCADE"), nullable=False
    )
    def_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False)
    executed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # 本次执行是否临时改过过滤条件（不修改定义本身）
    is_temporary_adjust: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
