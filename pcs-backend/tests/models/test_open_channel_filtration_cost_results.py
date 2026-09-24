"""P6-3 Task 30：3 张结果 ORM 字段冒烟。

校验 ORM stub 字段补齐（open_channel_results / filtration_results /
cost_est_results 的 P6-3 Task 30 派生列），不连 DB（SQLAlchemy 反射 / 类
属性读取）。
"""
from __future__ import annotations

from sqlalchemy import inspect

from app.models.calc import (
    CostEstResult,
    FiltrationResult,
    OpenChannelResult,
)

# OpenChannelResult P6-3 补齐派生字段（SPEC §3.2.6；Task 31 落库用）
_OPEN_CHANNEL_NEW_COLUMNS = (
    "critical_depth",
    "froude_number",
    "manning_n",
    "hydraulic_radius",
    "jump_type",
    "conjugate_depth",
    "energy_loss",
)
# 既有 7 字段（P6-3 Task 30 不漂移）
_OPEN_CHANNEL_LEGACY_COLUMNS = (
    "open_channel_id",
    "channel_type",
    "cross_section_json",
    "flow_rate",
    "depth",
    "velocity",
    "slope",
)

# FiltrationResult P6-3 补齐派生字段（SPEC §3.2.7；Task 33/34 落库用）
_FILTRATION_NEW_COLUMNS = (
    "media_type",
    "cake_resistance_alpha",
    "specific_resistance_r0",
    "permeability_k",
    "porosity_eps",
    "filter_velocity",
)
# 既有 4 字段（P6-3 Task 30 不漂移）
_FILTRATION_LEGACY_COLUMNS = (
    "filter_id",
    "filter_type",
    "area",
    "cycle_time",
    "pressure_drop",
)

# CostEstResult P6-3 补齐派生字段（SPEC §3.2.8；Task 35 落库用）
_COST_EST_NEW_COLUMNS = (
    "base_cost",
    "base_year",
    "cepci_index_base",
    "cepci_index_target",
    "correlation_source",
    "scaling_exponent",
)
# 既有 5 字段（P6-3 Task 30 不漂移）
_COST_EST_LEGACY_COLUMNS = (
    "cost_est_id",
    "equipment_id",
    "estimated_cost",
    "currency",
    "cost_index_year",
    "created_at",
)


def _orm_columns(model):
    """通过 SQLAlchemy Table 反射读取 ORM 字段名集合。"""
    return {c.key for c in inspect(model).columns}


def test_open_channel_result_orm_extends_task30_columns() -> None:
    """OpenChannelResult 必须含 Task 30 补齐 7 派生字段 + 既有 7 字段不漂移。

    SPEC §3.2.6：明渠均匀流+临界水深+水跃；critical_depth / froude_number /
    manning_n / hydraulic_radius + jump 三件套（jump_type / conjugate_depth /
    energy_loss）。
    """
    cols = _orm_columns(OpenChannelResult)
    # 既有 7 字段不漂移（红线 §5）
    for col in _OPEN_CHANNEL_LEGACY_COLUMNS:
        assert col in cols, f"OpenChannelResult 缺既有字段 {col}：{cols}"
    # 派生 7 字段齐
    for col in _OPEN_CHANNEL_NEW_COLUMNS:
        assert col in cols, f"OpenChannelResult 缺 Task 30 派生 {col}：{cols}"


def test_filtration_result_orm_extends_task30_columns() -> None:
    """FiltrationResult 必须含 Task 30 补齐 6 派生字段 + 既有 4 字段不漂移。

    SPEC §3.2.7：Ruth 恒压/恒速 + Ergun 深层过滤；media 五件套
    （media_type / cake_resistance_alpha / specific_resistance_r0 /
    permeability_k / porosity_eps）+ filter_velocity。
    """
    cols = _orm_columns(FiltrationResult)
    for col in _FILTRATION_LEGACY_COLUMNS:
        assert col in cols, f"FiltrationResult 缺既有字段 {col}：{cols}"
    for col in _FILTRATION_NEW_COLUMNS:
        assert col in cols, f"FiltrationResult 缺 Task 30 派生 {col}：{cols}"


def test_cost_est_result_orm_extends_task30_columns() -> None:
    """CostEstResult 必须含 Task 30 补齐 6 派生字段 + 既有 5 字段不漂移。

    SPEC §3.2.8：六十法则 + CEPCI 调整；base_cost / base_year /
    cepci_index_base / cepci_index_target + correlation_source +
    scaling_exponent。
    """
    cols = _orm_columns(CostEstResult)
    for col in _COST_EST_LEGACY_COLUMNS:
        assert col in cols, f"CostEstResult 缺既有字段 {col}：{cols}"
    for col in _COST_EST_NEW_COLUMNS:
        assert col in cols, f"CostEstResult 缺 Task 30 派生 {col}：{cols}"