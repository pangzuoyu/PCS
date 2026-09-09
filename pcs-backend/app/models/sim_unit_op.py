"""P3.x SIM-15: sim_unit_op_results + 6 专用结果表（单元 SUMMARY 存档）。

spec §5.5 + audit V2.0 E-1：
- sim_unit_op_results 主表：13 类单元操作（REACTOR/HX/PUMP/COLUMN/SIDESTRIPPER/MIXER/
  FLASH/VALVE/EXTRACTOR/COMPRESSOR/SPLITTER/STCA/CALCULATOR）的公共字段
  （uid/type/import_id/convergence_status/iterations/is_unreliable）
- 6 个专用结果表（1:1 FK → sim_unit_op_results.tower_id）：
  - SimReactorResult: conversion/conversion_basis/heat_duty/rxset_id/reactions_count/...
  - SimCstrResult:   residence_time / volume / temperature_k / ...
  - SimCompressorResult: outlet_pressure / work / efficiency / ...
  - SimSplitterResult: split_ratios_json (outlets)
  - SimStcaResult:   ovhd_stream / btms_stream / ...
  - SimCalculatorResult: sequence_streams_json / iterations

Pydantic/JSON 数据契约遵循 spec §3.4.2（PRO/II SUMMARY 段格式）。
FK：sim_unit_op_results.import_id → sim_imports.import_id（ON DELETE CASCADE）
索引：import_id（SIM-27 查询加速）+ unit_type（按类型过滤）

CSTR vs REACTOR：PRO/II 输出中 CSTR 是 REACTOR 子类型；
按 spec §5.5 拆为 2 表，但 SimReactorResult 仍兼容基本反应器（cstr 字段 nullable）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# ---------------------------------------------------------------------------
# 主表
# ---------------------------------------------------------------------------


class SimUnitOpResult(Base):
    """sim_unit_op_results 表：13 类单元操作 SUMMARY 公共字段（spec §5.5）。

    每条 PRO/II 单元定义 → 1 行（unit_uid 在 import 内唯一）。
    6 类专用字段下沉到专用表（SimReactorResult 等），本表只存公共 + raw_summary_json。
    """

    __tablename__ = "sim_unit_op_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_imports.import_id", ondelete="CASCADE"),
    )
    unit_uid: Mapped[str] = mapped_column(String(100))
    unit_type: Mapped[str] = mapped_column(String(30))
    convergence_status: Mapped[str | None] = mapped_column(String(30))
    iterations: Mapped[int | None] = mapped_column(Integer)
    # 完整 SUMMARY 段 JSON（下游 SIM-20 解析后可继续增强）
    raw_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    feed_streams_json: Mapped[list] = mapped_column(JSONB, default=list)
    product_streams_json: Mapped[list] = mapped_column(JSONB, default=list)
    # 不可靠标记（NOT_CONVERGED 单元 → 下游 P3.5 拒绝使用）
    is_unreliable: Mapped[bool] = mapped_column(Boolean, default=False)
    # 生命周期
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_sim_unit_op_results_import_id", "import_id"),
        Index("ix_sim_unit_op_results_unit_type", "unit_type"),
        # (import_id, unit_uid) 唯一 → 1 个单元只 1 行（PRO/II .out 内）
        Index(
            "uq_sim_unit_op_results_import_uid",
            "import_id",
            "unit_uid",
            unique=True,
        ),
    )


# ---------------------------------------------------------------------------
# 6 类专用结果表
# ---------------------------------------------------------------------------


class SimReactorResult(Base):
    """SimReactorResult：REACTOR（非 CSTR）专用字段（spec §5.5 + §3.4.2）。

    转换率 / 操作模式 / 反应集 / 反应数
    """

    __tablename__ = "sim_reactor_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    operation_mode: Mapped[str | None] = mapped_column(String(30))  # ADIABATIC / ISOTHERMAL / ...
    rxset_id: Mapped[str | None] = mapped_column(String(100))
    reactions_count: Mapped[int | None] = mapped_column(Integer)
    # 各反应转换率：[(reaction_id, conversion_value), ...]
    conversions_json: Mapped[list] = mapped_column(JSONB, default=list)


class SimCstrResult(Base):
    """SimCstrResult：CSTR 连续搅拌釜反应器专用字段（spec §5.5）。

    停留时间 / 反应器体积 / 出口温度
    """

    __tablename__ = "sim_cstr_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    residence_time_min: Mapped[float | None] = mapped_column(Float)
    volume_m3: Mapped[float | None] = mapped_column(Float)
    outlet_temperature_k: Mapped[float | None] = mapped_column(Float)


class SimCompressorResult(Base):
    """SimCompressorResult：COMPRESSOR 专用字段（spec §5.5）。

    出口压力 / 功 / 效率 / 多变指数
    """

    __tablename__ = "sim_compressor_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    outlet_pressure_kpa: Mapped[float | None] = mapped_column(Float)
    polytropic_exponent: Mapped[float | None] = mapped_column(Float)
    work_kw: Mapped[float | None] = mapped_column(Float)
    efficiency: Mapped[float | None] = mapped_column(Float)


class SimSplitterResult(Base):
    """SimSplitterResult：SPLITTER 分流器专用字段（spec §5.5）。

    多出口分流比（每个出口的流量或比例）
    """

    __tablename__ = "sim_splitter_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    # [{"stream_id", "mass_flow_kg_h", "mole_flow_kmol_h", "split_ratio"}, ...]
    outlets_json: Mapped[list] = mapped_column(JSONB, default=list)


class SimStcaResult(Base):
    """SimStcaResult：STCA（简捷精馏）专用字段（spec §5.5）。

    顶/底产品流 / 实际 / 最小回流比
    """

    __tablename__ = "sim_stca_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    ovhd_stream: Mapped[str | None] = mapped_column(String(100))
    btms_stream: Mapped[str | None] = mapped_column(String(100))
    actual_reflux_ratio: Mapped[float | None] = mapped_column(Float)
    min_reflux_ratio: Mapped[float | None] = mapped_column(Float)
    num_theoretical_stages: Mapped[int | None] = mapped_column(Integer)


class SimCalculatorResult(Base):
    """SimCalculatorResult：CALCULATOR 计算器专用字段（spec §5.5）。

    序列流列表（多个流按序送入计算）
    """

    __tablename__ = "sim_calculator_results"
    unit_op_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sim_unit_op_results.unit_op_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence_streams_json: Mapped[list] = mapped_column(JSONB, default=list)


__all__ = [
    "SimUnitOpResult",
    "SimReactorResult",
    "SimCstrResult",
    "SimCompressorResult",
    "SimSplitterResult",
    "SimStcaResult",
    "SimCalculatorResult",
]
