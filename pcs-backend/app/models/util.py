"""S1-5 R1: UtilResults ORM (util_results 单表) + jsonb_deprecated marker。

Per SPEC V1.4 §4.4 + plan brief Step 3：13 类公用工程枚举（consumption_json
JSONB 存 per-category quantity）+ jsonb_deprecated bool（默认 False；Sprint 1
JSONB 权威，Sprint 2 起置 True 当 5 表迁移完成后）。

Sprint 2 Task S2-1~6 在此文件 append 独立表；本任务仅落 V1.3 基线 + 折标煤
计算路径。

⚠️ **表清单变更 (用户裁决 2026-10-05)**: 原计划的 5 表含 ``catalyst_loading``
（催化剂装填量），**该功能已取消，不建表**。P7-6B 收尾又新增 2 张
（``utility_gas_media`` / ``utility_low_temp_heat``），故权威表清单现为 **6 张**：

    utility_power_items      T1 电耗 (kWh)
    utility_fuel_gas         T2 燃料气 (Nm³)
    utility_heat_exchange    T3 蒸汽 + 9 类水 (t)
    utility_gas_media        工艺气体/氮气/仪表空气 (Nm³)      ← P7-6B 收尾新增
    utility_low_temp_heat    低温余热回收 (GJ)                  ← P7-6B 收尾新增
    utility_energy_summary   T5 综合能耗汇总

详见 docs/PCS-NOTE-catalyst_loading-取消-2026-10-05.md。
"""

from __future__ import annotations

import datetime
import uuid
from datetime import date

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
      当权威表清单 6 张 (utility_power_items / utility_fuel_gas /
      utility_heat_exchange / utility_gas_media / utility_low_temp_heat /
      utility_energy_summary) 全部迁移完成且数据回填后
      （catalyst_loading 已于 2026-10-05 用户裁决取消，不建表）
    - 13 类公用工程清单 + 单位见 ``app/services/util/category_map.py``
    - 折标煤通过 ``ToeConversionService`` 查询 + 13→6 fuel_type 映射计算
    """

    __tablename__ = "util_results"
    __table_args__ = (
        Index("ix_util_results_project", "project_id"),
        # F-P1-001 fix: 加 (project_id, workspace_id) 复合索引 — 跨 workspace
        # 过滤查询 (project_id, workspace_id) 走复合索引避免回表
        Index("ix_util_results_project_workspace", "project_id", "workspace_id"),
        Index("ix_util_results_workspace", "workspace_id"),
        CheckConstraint(
            "cooling_water_consumption_t_yr IS NULL OR cooling_water_consumption_t_yr >= 0",
            name="ck_util_results_cooling_water_non_negative",
        ),
        CheckConstraint(
            "electrical_power_kwh_yr IS NULL OR electrical_power_kwh_yr >= 0",
            name="ck_util_results_electrical_power_non_negative",
        ),
        CheckConstraint(
            "fuel_gas_consumption_nm3_yr IS NULL OR fuel_gas_consumption_nm3_yr >= 0",
            name="ck_util_results_fuel_gas_non_negative",
        ),
        CheckConstraint(
            "steam_consumption_t_yr IS NULL OR steam_consumption_t_yr >= 0",
            name="ck_util_results_steam_non_negative",
        ),
    )

    util_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
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

    # F-P1-007 fix: 4 新聚合列 (annual_total_energy + total_toe +
    # total_standard_coal_kg + tolerance_status), 让 UtilResults
    # 也包含 T5 综合能耗汇总结果 (与 utility_energy_summary 并行)
    annual_total_energy: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年总能耗 (MJ/yr; canonical unit, F-P1-007 同步 UtilityEnergySummary)",
    )
    total_toe: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年折标油 (toe; F-P1-007 同步 UtilityEnergySummary)",
    )
    total_standard_coal_kg: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="年折标煤 (kg 标煤; F-P1-007 同步 UtilityEnergySummary)",
    )
    tolerance_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        comment="容差状态 NA/OK/EXCEEDED (F-P1-007 + F-P0-004 server_default='NA' 一致)",
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
        CheckConstraint(
            "annual_consumption_kwh >= 0",
            name="ck_utility_power_items_consumption_non_negative",
        ),
        CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_power_items_hours_in_year",
        ),
        CheckConstraint(
            "load_factor > 0 AND load_factor <= 1",
            name="ck_utility_power_items_load_factor_range",
        ),
        CheckConstraint(
            "motor_power_kw > 0",
            name="ck_utility_power_items_motor_power_positive",
        ),
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
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False,
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
        Index("ix_utility_fuel_gas_gas_source", "gas_source"),
        CheckConstraint(
            "annual_consumption_nm3 >= 0",
            name="ck_utility_fuel_gas_annual_consumption_non_negative",
        ),
        CheckConstraint(
            "calorific_value_kcal_nm3 > 0 AND calorific_value_kcal_nm3 <= 20000",
            name="ck_utility_fuel_gas_calorific_value_range",
        ),
        CheckConstraint(
            "consumption_nm3_h > 0",
            name="ck_utility_fuel_gas_consumption_positive",
        ),
        CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_fuel_gas_hours_in_year",
        ),
        CheckConstraint(
            "operating_phase IN ('INITIAL', 'STEADY', 'MAX')",
            name="ck_utility_fuel_gas_operating_phase_enum",
        ),
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
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False,
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
        comment="燃料类型: NATURAL_GAS / REFINERY_GAS / LPG / LNG / OTHERS "
                "(R0 deprecated; R1 §7.3 新增 gas_source 3 类)",
    )
    gas_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "气源分类 (R1 §7.3 GB 30251-2024 附录A): "
            "OILFIELD_GAS (油田气 0.93 kg标油/Nm³) / GASFIELD_GAS (气田气 0.85) / "
            "REFINERY_FUEL_GAS (炼厂燃料气 950 kg标油/t)"
        ),
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
        Index("ix_utility_heat_exchange_medium_type", "medium_type"),
        Index("ix_utility_heat_exchange_pressure_level", "pressure_level"),
        CheckConstraint(
            "annual_consumption_t >= 0",
            name="ck_utility_heat_exchange_annual_consumption_non_negative",
        ),
        CheckConstraint(
            "operating_hours_per_year > 0 AND operating_hours_per_year <= 8760",
            name="ck_utility_heat_exchange_hours_in_year",
        ),
        CheckConstraint(
            "steam_pressure_mpa_gauge > 0",
            name="ck_utility_heat_exchange_pressure_positive",
        ),
        CheckConstraint(
            "steam_quality_pct >= 0 AND steam_quality_pct <= 100",
            name="ck_utility_heat_exchange_quality_pct_range",
        ),
        CheckConstraint(
            "return_condensate_pct >= 0 AND return_condensate_pct <= 100",
            name="ck_utility_heat_exchange_return_condensate_pct_range",
        ),
        CheckConstraint(
            "temperature_class IN ('LP', 'MP', 'HP', 'ULTRA_HIGH')",
            name="ck_utility_heat_exchange_temperature_class_enum",
        ),
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
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False,
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
            "LP 0.3~0.8 / MP 1.0~2.5 / HP 3.5~10 / ULTRA_HIGH >10) "
            "(R0 deprecated; R1 §7.1 新增 pressure_level 9 档)"
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
        comment="蒸汽温度等级: LP (低压) / MP (中压) / HP (高压) / ULTRA_HIGH (超高压) "
                "(R0 deprecated; R1 §7.1 新增 pressure_level 9 档)",
    )
    pressure_level: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "蒸汽压力等级 (R1 §7.1 GB 30251-2024 附录A 9 档): "
            "GE_7_0_MPA / 4_5_TO_7_0_MPA / 3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / "
            "1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / 0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / "
            "LT_0_3_MPA"
        ),
    )
    medium_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "介质类型 (R1 §7.2): STEAM / FRESH_WATER / CIRCULATING_WATER / "
            "SOFTENED_WATER / DEMINERALIZED_WATER / LP_DEAERATED_WATER / "
            "HP_DEAERATED_WATER / TURBINE_CONDENSATE / 120C_CONDENSATE_TREATED / "
            "120C_CONDENSATE_REUSABLE"
        ),
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
        CheckConstraint(
            "standard_coal_factor > 0",
            name="ck_utility_energy_summary_coal_factor_positive",
        ),
        CheckConstraint(
            "toe_conversion_factor > 0",
            name="ck_utility_energy_summary_toe_factor_positive",
        ),
        CheckConstraint(
            "tolerance_status IN ('OK', 'EXCEEDED', 'NA')",
            name="ck_utility_energy_summary_tolerance_status_enum",
        ),
        CheckConstraint(
            "tolerance_status <> 'EXCEEDED' OR (tolerance_pct IS NOT NULL AND tolerance_pct > 2.0)",
            name="ck_utility_energy_summary_tolerance_status_exceeded_has_pct",
        ),
        CheckConstraint(
            "tolerance_status <> 'OK' OR (tolerance_pct IS NOT NULL AND tolerance_pct <= 2.0)",
            name="ck_utility_energy_summary_tolerance_status_ok_has_pct",
        ),
        CheckConstraint(
            "total_standard_coal_kg >= 0",
            name="ck_utility_energy_summary_total_coal_non_negative",
        ),
        CheckConstraint(
            "annual_total_energy >= 0",
            name="ck_utility_energy_summary_total_non_negative",
        ),
        CheckConstraint(
            "total_toe >= 0",
            name="ck_utility_energy_summary_total_toe_non_negative",
        ),
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
        comment="工作区 ID (FK workspaces.workspace_id; 工作区删除时汇总跟随删除 —— "
                "如需保留数据请走归档而非删除)",
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
    electricity_value_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        comment=(
            "电当量值/等价值选择 (R1 §5 GB 30251-2024 §6.1.1): "
            "EQUIVALENT (当量值 0.086 kg标油/kWh - 其他产品用) / "
            "EQUIVALENT_VALUE (等价值 0.21 kg标油/kWh - 炼油/乙烯用); "
            "NULL = 默认 EQUIVALENT"
        ),
    )
    r1_classification_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment=(
            "R1 分类聚合结果 (F-P0-001 R1 §7): "
            "{steam_by_pressure_level: {GE_7_0_MPA: float}, "
            "fuel_gas_by_source: {OILFIELD_GAS: float}, "
            "water_by_type: {FRESH_WATER: float}}; "
            "null = R0 单值聚合 (向后兼容)"
        ),
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
        # F-P0-004 fix: server_default='NA' (无 XLS 参考默认), 不用 'OK'
        # 避免 compliance audit 误读 'OK' 为 'computed and within 2%' 假阴性
        String(16), nullable=False, server_default="NA",
        comment="容差校验状态: OK (≤2%) / EXCEEDED (>2%) / NA (无 XLS 参考)",
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


class UtilityGasMedia(Base):
    """工艺气体 / 氮气 / 仪表空气消耗 (P7-6B 收尾, 单位 Nm³).

    业务 (GB 30251-2024 附录A 表A.1 序号 31/32/33 + R1 GAS 行):

    - 承载 `_aggregate_util_subtables` 长期缺失的 `gas_nm3_yr` —— 该字段此前
      是硬编码 `None`, 而 CONFIG 里 NITROGEN / INSTRUMENT_AIR / GAS 的系数
      一直存在却从无代码读取 (死数据)。
    - `gas_medium` (GasMedium) 判别介质 → 决定查 CONFIG 的哪一行 (见 GasMedium
      docstring 的映射表)。**净化空气 0.038 与氮气 0.15 差近 4 倍, 串行即高估。**
    - 不与 `utility_fuel_gas` 重叠: 后者是燃料气 (有热值、按 gas_source 3 类),
      本表是非燃料气体介质 (制氮/仪表风/厂区风/工艺气体)。

    不继承 TaggedRecordMixin (公用工程记录)。
    """

    __tablename__ = "utility_gas_media"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "equipment_tag", "gas_medium",
            name="uq_utility_gas_media_project_equipment_medium",
        ),
        CheckConstraint(
            "gas_medium IN ('PROCESS_GAS', 'NITROGEN', 'PURIFIED_AIR', "
            "'NON_PURIFIED_AIR', 'PLANT_AIR')",
            name="ck_utility_gas_media_medium",
        ),
        CheckConstraint(
            "consumption_nm3_h >= 0 AND annual_consumption_nm3 >= 0",
            name="ck_utility_gas_media_nonneg",
        ),
        Index("ix_utility_gas_media_project", "project_id"),
        Index("ix_utility_gas_media_workspace", "workspace_id"),
        Index("ix_utility_gas_media_gas_medium", "gas_medium"),
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
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False,
        comment="工作区 ID (FK workspaces.workspace_id)",
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("equipment_list.equipment_id", ondelete="SET NULL"), nullable=True,
        comment="设备 ID (FK equipment_list.equipment_id)",
    )
    equipment_tag: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="设备位号 (与 gas_medium 联合 UNIQUE)",
    )
    gas_medium: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment=(
            "气体介质 (GasMedium): PROCESS_GAS (工艺气体 0.85) / "
            "NITROGEN (氮气 0.15, 附录A 序号33) / "
            "PURIFIED_AIR (净化压缩空气 0.038, 序号31) / "
            "NON_PURIFIED_AIR (非净化 0.028, 序号32) / "
            "PLANT_AIR (厂区空气, 按非净化 0.028)"
        ),
    )
    consumption_nm3_h: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="小时消耗量 (Nm³/h)",
    )
    operating_hours_per_year: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="8000",
        comment="年运行小时数 (h/yr; ≤ 8760)",
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


class UtilityLowTempHeat(Base):
    """低温余热回收 (P7-6B 收尾, 单位 GJ).

    业务 (GB 30251-2024 附录A 表A.1 序号 34):

    - 承载 `_aggregate_util_subtables` 长期缺失的 `low_temp_heat_gj_yr` ——
      该字段此前是硬编码 `None`, 且 service 还有一个**硬编码错误系数**兜底
      (0.0341 kg标油/MJ, 偏离标准 +184.2% 且量纲错, 已于 bug-135 删除)。
    - 附录A 序号34 低温热 = **0.012 kg标油/MJ** (= 0.5 MJ/MJ 可回收率)。
    - 单位是 GJ 而非 Nm³/t, 故独立成表, 不与 utility_gas_media 合并。

    不继承 TaggedRecordMixin (公用工程记录)。
    """

    __tablename__ = "utility_low_temp_heat"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "equipment_tag",
            name="uq_utility_low_temp_heat_project_equipment",
        ),
        CheckConstraint(
            "heat_recovery_gj_h >= 0 AND annual_recovered_heat_gj >= 0",
            name="ck_utility_low_temp_heat_nonneg",
        ),
        Index("ix_utility_low_temp_heat_project", "project_id"),
        Index("ix_utility_low_temp_heat_workspace", "workspace_id"),
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
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"), nullable=False,
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
    heat_recovery_gj_h: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="小时回收热量 (GJ/h)",
    )
    operating_hours_per_year: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="8000",
        comment="年运行小时数 (h/yr; ≤ 8760)",
    )
    annual_recovered_heat_gj: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment=(
            "年回收热量 (GJ/yr; = heat_recovery_gj_h × operating_hours_per_year)。"
            "折标: × 1000 (GJ→MJ) × 0.012 kg标油/MJ (附录A 序号34)"
        ),
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
