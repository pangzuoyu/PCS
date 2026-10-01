"""S1-5 R1: UtilResults ORM (util_results 单表) + jsonb_deprecated marker。

Per SPEC V1.4 §4.4 + plan brief Step 3：13 类公用工程枚举（consumption_json
JSONB 存 per-category quantity）+ jsonb_deprecated bool（默认 False；Sprint 1
JSONB 权威，Sprint 2 起置 True 当 5 表迁移完成后）。

Sprint 2 Task S2-1~6 会在此文件 append 5 张独立表（utility_power_items /
utility_fuel_gas / utility_heat_exchange / utility_energy_summary /
catalyst_loading）；本任务仅落 V1.3 基线 + 折标煤计算路径。
"""

from __future__ import annotations

import datetime
import uuid
from datetime import date

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class UtilResults(TimestampMixin, Base):
    """UTIL V1.3 基线表（util_results，per SPEC V1.4 §4.4 + plan brief）。

    业务：
    - ``consumption_json`` 存 13 类公用工程消耗量（flat {category: float_quantity}）
    - ``jsonb_deprecated`` 默认 False（Sprint 1 JSONB 权威）；Sprint 2 起置 True
      当 5 表 (utility_power_items / utility_fuel_gas / utility_heat_exchange /
      utility_energy_summary / catalyst_loading) 全部迁移完成且数据回填后
    - 13 类公用工程清单 + 单位见 ``app/services/util/category_map.py``
    - 折标煤通过 ``ToeConversionService`` 查询 + 13→6 fuel_type 映射计算
    """

    __tablename__ = "util_results"
    __table_args__ = (
        Index("ix_util_results_project", "project_id"),
    )

    util_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id"), index=True
    )

    # 业务日期（折标煤按年查询需要）
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 13 类消耗量（JSONB；SQLite 测试时 conftest 映射 JSON）
    consumption_json: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        comment="13 类公用工程 flat {category: float_quantity} map (per SPEC V1.4 §4.4)",
    )

    # Sprint 1 JSONB 权威；Sprint 2 起置 True 当 5 表迁移完成
    jsonb_deprecated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Sprint 1 False JSONB 权威；Sprint 2 起 True 表示已迁移 5 表",
    )

    # T4 auxiliary_consumption 4 字段（聚合 T1/T2/T3 子表 annual_consumption +
    # cooling_water 子表待立；Sprint 1 存量数据 NULL；service 层 fallback 到
    # consumption_json JSONB 取值（D1 裁决 1A：5 表权威 + JSONB deprecated））
    electrical_power_kwh_yr: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="年用电量 (kWh/yr; 聚合 utility_power_items.annual_consumption_kwh)",
    )
    fuel_gas_consumption_nm3_yr: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="年燃料气消耗量 (Nm³/yr; 聚合 utility_fuel_gas.annual_consumption_nm3)",
    )
    steam_consumption_t_yr: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="年蒸汽消耗量 (t/yr; 聚合 utility_heat_exchange.annual_consumption_t)",
    )
    cooling_water_consumption_t_yr: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="年冷却水消耗量 (t/yr; 待 P7-6B 冷却水子表落地后聚合)",
    )

    # 元信息
    source: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="数据来源描述（GB 2589 / 项目实际 / 设计值）",
    )


class UtilityPowerItem(Base):
    """电耗设备清单 (P7 Sprint 2 T1 / P7-OPEN-009 §1 #1).

    业务 (P7 SPEC V1.4 §3.2.2(5) + §4.6):

    - 存电耗设备清单 (PUMP / COMPRESSOR / FAN 等旋转设备) 的电机功率 +
      年运行小时 + 负荷率 → 年用电量。
    - 4 业务字段：motor_power_kw / operating_hours_per_year / load_factor /
      annual_consumption_kwh + 4 CHECK 约束 (数值范围)。
    - FK equipment_id → equipment_list.equipment_id (nullable：PMS 早期
      数据可能未关联到 equipment_list 主表)。
    - UNIQUE(project_id, equipment_tag) 防重复录入。
    - annual_consumption_kwh = motor_power_kw × operating_hours_per_year ×
      load_factor (service 层计算，DB 存计算结果便于直接查询)。

    不继承 TaggedRecordMixin (公用工程记录，非业务计算 tagged 记录)。
    """

    __tablename__ = "utility_power_items"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_power_items_project_equipment_tag",
        ),
        Index("ix_utility_power_items_project", "project_id"),
        Index("ix_utility_power_items_workspace", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键 (uuid.uuid4 default)",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False,
        comment="项目 ID (FK projects.project_id)",
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False,
        comment="工作区 ID (FK workspaces.workspace_id)",
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"), nullable=True,
        comment="设备 ID (FK equipment_list.equipment_id; nullable: PMS 早期数据可能未关联)",
    )
    equipment_tag: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="设备位号 (项目内唯一)",
    )
    motor_power_kw: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="电机额定功率 (kW; PUMP AbsorbedPower)",
    )
    operating_hours_per_year: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年运行小时数 (h/yr; ≤ 8760)",
    )
    load_factor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="负荷率 (无量纲; 0 < load_factor ≤ 1)",
    )
    annual_consumption_kwh: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年用电量 (kWh/yr; = motor_power × hours × load_factor)",
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="MANUAL",
        comment="数据来源: PMS (设备管理系统) / MANUAL (手动录入) / CALC (计算)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="记录创建时间 (DB server_default)",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True,
        comment="记录更新时间 (ORM onupdate 触发)",
    )


class UtilityFuelGas(Base):
    """燃料气消耗 (P7 Sprint 2 T2 / P7-OPEN-009 §1 #2).

    业务 (P7 SPEC V1.4 §3.2.2(5) + §4.6):

    - 存燃料气 (natural gas / refinery gas / LPG / LNG 等) 消耗量
      含热值 + 小时消耗量 + 年消耗量。
    - 业务字段：fuel_type / calorific_value_kcal_nm3 / consumption_nm3_h /
      operating_phase (INITIAL/STEADY/MAX 初期/末期/最大工况) /
      operating_hours_per_year / annual_consumption_nm3 + 5 CHECK 约束。
    - FK equipment_id → equipment_list.equipment_id (nullable)。
    - UNIQUE(project_id, equipment_tag, operating_phase) 每设备每工况 1 行。
    - annual_consumption_nm3 = consumption_nm3_h × operating_hours_per_year
      (service 层计算 + DB 存结果)。

    不继承 TaggedRecordMixin (公用工程记录)。
    """

    __tablename__ = "utility_fuel_gas"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "equipment_tag", "operating_phase",
            name="uq_utility_fuel_gas_project_equipment_phase",
        ),
        Index("ix_utility_fuel_gas_project", "project_id"),
        Index("ix_utility_fuel_gas_workspace", "workspace_id"),
        Index("ix_utility_fuel_gas_fuel_type", "fuel_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键 (uuid.uuid4 default)",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False,
        comment="项目 ID (FK projects.project_id)",
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False,
        comment="工作区 ID (FK workspaces.workspace_id)",
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"), nullable=True,
        comment="设备 ID (FK equipment_list.equipment_id)",
    )
    equipment_tag: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="设备位号 (项目内唯一, 与 operating_phase 联合 UNIQUE)",
    )
    fuel_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="NATURAL_GAS",
        comment="燃料类型: NATURAL_GAS / REFINERY_GAS / LPG / LNG / OTHERS",
    )
    calorific_value_kcal_nm3: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="低位热值 (kcal/Nm³; 典型天然气 8000~9000)",
    )
    consumption_nm3_h: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="小时消耗量 (Nm³/h)",
    )
    operating_phase: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="操作工况: INITIAL (初期) / STEADY (末期/稳态) / MAX (最大工况)",
    )
    operating_hours_per_year: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="8000",
        comment="该工况年运行小时数 (h/yr; ≤ 8760)",
    )
    annual_consumption_nm3: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年消耗量 (Nm³/yr; = consumption_nm3_h × operating_hours_per_year)",
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="MANUAL",
        comment="数据来源: PMS / MANUAL / CALC",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="记录创建时间 (DB server_default)",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True,
        comment="记录更新时间 (ORM onupdate 触发)",
    )


class UtilityHeatExchange(Base):
    """蒸汽 / 冷凝水 (P7 Sprint 2 T3 / P7-OPEN-009 §1 #3).

    业务 (P7 SPEC V1.4 §3.2.2(5) + §4.6):

    - 存蒸汽 (HP/MP/LP/ULTRA_HIGH 等级) + 冷凝水消耗 / 回收数据。
    - 业务字段：steam_pressure_mpa_gauge / steam_quality_pct /
      return_condensate_pct / temperature_class enum (LP/MP/HP/ULTRA_HIGH)
      / steam_consumption_t_h / operating_hours_per_year /
      annual_consumption_t + 6 CHECK 约束。
    - FK equipment_id → equipment_list.equipment_id (nullable)。
    - UNIQUE(project_id, equipment_tag) 防重复录入。
    - annual_consumption_t = steam_consumption_t_h × operating_hours_per_year
      (service 层计算 + DB 存结果)。

    不继承 TaggedRecordMixin (公用工程记录)。
    """

    __tablename__ = "utility_heat_exchange"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_heat_exchange_project_equipment_tag",
        ),
        Index("ix_utility_heat_exchange_project", "project_id"),
        Index("ix_utility_heat_exchange_workspace", "workspace_id"),
        Index("ix_utility_heat_exchange_temperature_class", "temperature_class"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键 (uuid.uuid4 default)",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False,
        comment="项目 ID (FK projects.project_id)",
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False,
        comment="工作区 ID (FK workspaces.workspace_id)",
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"), nullable=True,
        comment="设备 ID (FK equipment_list.equipment_id)",
    )
    equipment_tag: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="设备位号 (项目内唯一)",
    )
    steam_pressure_mpa_gauge: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment=(
            "蒸汽压力 (MPa 表压 gauge; "
            "LP 0.3~0.8 / MP 1.0~2.5 / HP 3.5~10 / ULTRA_HIGH >10)"
        ),
    )
    steam_quality_pct: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="蒸汽干度 (% dryness; 0~100)",
    )
    return_condensate_pct: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="冷凝水回收率 (% condensate return; 0~100)",
    )
    temperature_class: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="蒸汽温度等级: LP (低压) / MP (中压) / HP (高压) / ULTRA_HIGH (超高压)",
    )
    steam_consumption_t_h: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="小时蒸汽消耗量 (t/h)",
    )
    operating_hours_per_year: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="8000",
        comment="年运行小时数 (h/yr; ≤ 8760)",
    )
    annual_consumption_t: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment=(
            "年蒸汽消耗量 (t/yr; "
            "= steam_consumption_t_h × operating_hours_per_year)"
        ),
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="MANUAL",
        comment="数据来源: HEAT 汇总 / PMS / MANUAL / CALC",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="记录创建时间 (DB server_default)",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True,
        comment="记录更新时间 (ORM onupdate 触发)",
    )


class UtilityEnergySummary(Base):
    """综合能耗汇总 (P7 Sprint 2 T5 / P7-OPEN-009 §1 #4).

    业务 (P7 SPEC V1.4 §3.2.2(5) + §4.6):

    - 存项目年度综合能耗汇总 (折标油 + 折标煤).
    - 业务字段: 6 类能源 annual 消耗 (electricity/fuel_gas/steam/water/
      gas/low_temp_heat) + 3 spec 字段 (annual_total_energy /
      toe_conversion_factor / standard_coal_factor) + 2 derived
      (total_toe / total_standard_coal_kg) + 2 容差 (tolerance_pct /
      tolerance_status).
    - 聚合 service: T1 utility_power_items + T2 utility_fuel_gas +
      T3 utility_heat_exchange + cooling_water 待 P7-6B + 折标系数
      ConfigEnergyConversionFactor (5-min TTL 缓存).
    - 容差校验 ≤2% per P7-OPEN-009 §6.
    - FK project_id / workspace_id CASCADE.
    - UNIQUE(project_id, business_year, source) 同源同年防重复.
    - 不继承 TaggedRecordMixin.
    """

    __tablename__ = "utility_energy_summary"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "business_year", "source",
            name="uq_utility_energy_summary_project_year_source",
        ),
        Index("ix_utility_energy_summary_project", "project_id"),
        Index("ix_utility_energy_summary_workspace", "workspace_id"),
        Index("ix_utility_energy_summary_year", "business_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键 (uuid.uuid4 default)",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=False,
        comment="项目 ID (FK projects.project_id)",
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="CASCADE"), nullable=False,
        comment="工作区 ID (FK workspaces.workspace_id)",
    )
    business_year: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="业务年度 (e.g., 2026; summary 是 annual aggregation)",
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="CALCULATION",
        comment="数据来源: CALCULATION / XLS_REFERENCE",
    )
    electricity_kwh_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年用电量 (kWh/yr; 聚合 utility_power_items)",
    )
    fuel_gas_nm3_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年燃料气消耗量 (Nm³/yr; 聚合 utility_fuel_gas)",
    )
    steam_t_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年蒸汽消耗量 (t/yr; 聚合 utility_heat_exchange)",
    )
    water_t_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年新鲜水消耗量 (t/yr; 待 P7-6B 冷却水子表落地)",
    )
    gas_nm3_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年工艺气体消耗量 (Nm³/yr; 预留字段)",
    )
    low_temp_heat_gj_yr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年低温余热 (GJ/yr; 预留字段)",
    )
    annual_total_energy: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年度总能耗 (MJ/yr; canonical unit)",
    )
    toe_conversion_factor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="聚合折标油系数 (kg 标油/MJ)",
    )
    standard_coal_factor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="聚合折标煤系数 (kg 标煤/MJ)",
    )
    total_toe: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年度折标油总量 (tonne oil equivalent)",
    )
    total_standard_coal_kg: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="年度折标煤总量 (kg 标煤)",
    )
    tolerance_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="容差 (vs XLS_REFERENCE; ≤2% per P7-OPEN-009 §6)",
    )
    tolerance_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="OK",
        comment="容差校验状态: OK / EXCEEDED / NA",
    )
    computed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="服务计算时间 (DB server_default)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="记录创建时间 (DB server_default)",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True,
        comment="记录更新时间 (ORM onupdate 触发)",
    )
