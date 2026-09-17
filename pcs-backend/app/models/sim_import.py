"""P3.x SIM-14: sim_imports + sim_import_warnings 表（stateful preview，D-4 等价闭环）。

spec §5.5 + 用户 2026-09-09 裁决：
- preview 阶段：解析后写入 sim_imports（状态=PREVIEW，含解析结果 JSON），返回 import_id
- commit 阶段：通过 import_id 读取 sim_imports，校验未过期，落库后更新状态=COMMITTED
- 24h 过期机制：expires_at = created_at + 24h

D-4 闭环条件：sim_imports.import_id 在 preview 阶段生成并持久化。
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimImportType(str, enum.Enum):
    """导入来源类型。"""

    PROII = "PROII"
    EXCEL = "EXCEL"


class SimImportStatus(str, enum.Enum):
    """导入生命周期状态。"""

    PREVIEW = "PREVIEW"
    COMMITTED = "COMMITTED"
    EXPIRED = "EXPIRED"


class SimImportWarningSeverity(str, enum.Enum):
    """warning 严重等级。"""

    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


class SimImport(Base):
    """sim_imports 表：每次 PRO/II / Excel 导入的 preview 持久化（spec §5.5）。

    preview 阶段：status=PREVIEW，含 preview_streams_json + conflict_report_json + warnings_json
    commit 阶段：status=COMMITTED，记录 committed_at + committed_by
    24h 后：status=EXPIRED（commit 时校验）
    """

    __tablename__ = "sim_imports"
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.project_id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workspaces.workspace_id", ondelete="RESTRICT")
    )
    import_type: Mapped[SimImportType] = mapped_column(
        SAEnum(
            SimImportType,
            name="simimporttype",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    status: Mapped[SimImportStatus] = mapped_column(
        SAEnum(
            SimImportStatus,
            name="simimportstatus",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    source_file_name: Mapped[str] = mapped_column(String(500))
    convergence_status: Mapped[str | None] = mapped_column(String(30))
    banner_version: Mapped[str | None] = mapped_column(String(20))
    # preview 阶段解析结果（commit 阶段读取使用）
    preview_streams_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    preview_towers_json: Mapped[list] = mapped_column(JSONB, default=list)
    conflict_report_json: Mapped[dict | None] = mapped_column(JSONB)
    warnings_json: Mapped[list] = mapped_column(JSONB, default=list)
    # 生命周期
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    committed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    warnings: Mapped[list[SimImportWarning]] = relationship(
        back_populates="sim_import",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_sim_imports_project_status", "project_id", "status"),
        Index("ix_sim_imports_expires_at", "expires_at"),
    )


class SimImportWarning(Base):
    """sim_import_warnings 表：preview 阶段 warning 行级存档（spec §5.5）。"""

    __tablename__ = "sim_import_warnings"
    warning_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_imports.import_id", ondelete="CASCADE"),
    )
    severity: Mapped[SimImportWarningSeverity] = mapped_column(
        SAEnum(
            SimImportWarningSeverity,
            name="simimportwarningseverity",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        )
    )
    unit_id: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sim_import: Mapped[SimImport] = relationship(back_populates="warnings")


__all__ = [
    "SimImport",
    "SimImportStatus",
    "SimImportType",
    "SimImportWarning",
    "SimImportWarningSeverity",
]
