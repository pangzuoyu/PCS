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
