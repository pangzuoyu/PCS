"""物流符号表 ORM（SUP-002 §7.1/§7.2）。"""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class StreamSymbol(TimestampMixin, Base):
    """公司级流股符号（stream_symbols 表，SUP-002 §7.1）。

    业务：symbol 字段全局唯一（如物料流/能量流/控制信号等类型化符号）；
    asset_id 反向追溯所属配置资产；is_active 控制可见性（默认 True）。
    """

    __tablename__ = "stream_symbols"
    symbol_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    version: Mapped[str] = mapped_column(String(50), default="1")


class ProjectStreamSymbol(TimestampMixin, Base):
    """项目级流股符号（project_stream_symbols 表，SUP-002 §7.2）。

    业务：UNIQUE(project_id, symbol) 限定项目内符号唯一；source_symbol_id
    可空（项目自定义）；snapshot_json 是 fork 时公司级快照；override_json
    项目级重写（颜色/icon/排序等 UI 属性）。
    """

    __tablename__ = "project_stream_symbols"
    __table_args__ = (
        UniqueConstraint("project_id", "symbol", name="uq_project_stream_symbol"),
    )
    project_symbol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.project_id"))
    source_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stream_symbols.symbol_id"), nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    override_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")