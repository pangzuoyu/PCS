"""P3.x SIM-16: sim_tower_results 表（COLUMN SUMMARY 存档）。

spec §5.5 + audit V2.0 E-1：
- 每条 COLUMN 单元操作 → 1 行 sim_tower_results
- 元数据：tower_uid / tower_name / num_stages / condenser / reboiler / feeds / products
- 4 类 JSON 数据：tray_data_json / compositions_json / loading_json / rating_json
- FK：sim_tower_results.import_id → sim_imports.import_id（ON DELETE CASCADE）
- 索引：(import_id) 加速查询 SIM-27（9 类 sim imports 查询端点）

Pydantic/JSON 数据契约遵循 spec §3.4.2（单元操作 SUMMARY 段）：
- tray_data_json：每板 {stage, temp_k, pressure_kpa, liquid_flow, vapor_flow}
- compositions_json：每板组分分布 {stage_N: {LIBID: mole_frac}}
- loading_json：每板水力学 {stage_N: {vapor_load, liquid_load, ...}}
- rating_json：每板评价 {stage_N: {flood_factor, ...}} + overall 摘要
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimTowerResult(Base):
    """sim_tower_results 表：PRO/II COLUMN 单元 SUMMARY 段存档（spec §5.5）。

    每条 COLUMN / SIDESTRIPPER 单元操作 → 1 行
    SIDESTRIPPER 也归入此表（is_side_draw=True 区分）
    """

    __tablename__ = "sim_tower_results"
    tower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_imports.import_id", ondelete="CASCADE"),
    )
    # 基础元数据
    tower_uid: Mapped[str] = mapped_column(String(100))
    tower_name: Mapped[str | None] = mapped_column(String(200))
    tower_type: Mapped[str] = mapped_column(String(30))  # COLUMN / SIDESTRIPPER
    num_stages: Mapped[int | None] = mapped_column(Integer)
    condenser_type: Mapped[str | None] = mapped_column(String(30))  # TOTAL / PARTIAL / NONE
    reboiler_type: Mapped[str | None] = mapped_column(String(30))  # KETTLE / THERMOSYPHON / NONE
    # 关联流（JSONB 数组）
    feed_stages_json: Mapped[list] = mapped_column(JSONB, default=list)
    product_streams_json: Mapped[list] = mapped_column(JSONB, default=list)
    # 4 类 JSON 数据
    tray_data_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    compositions_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    loading_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    rating_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    # 不可靠标记（NOT_CONVERGED 单元的下游产品 P3.5 需拒绝使用）
    is_unreliable: Mapped[bool] = mapped_column(default=False)
    # 生命周期
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_sim_tower_results_import_id", "import_id"),)


__all__ = ["SimTowerResult"]
