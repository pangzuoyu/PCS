"""成本指数 / 元数据型 CONFIG 表（与 config_domain 的业务配置域区分）。

包含 CEPCI（Chemical Engineering Plant Cost Index）年度指数等成本/物价类
元数据，被 COST_EST 模块（P6-3）读取做费用估算。此类表是「元数据」而非
业务计算记录，故不继承 TaggedRecordMixin/record_hash（P6 计划 Task 17）。

如需新增同类型元数据 CONFIG 表（汇率 / 区域人工时薪 / 设备价指数等），
按统一模式追加到本文件即可。
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CepciIndexSeries(Base):
    """CEPCI 年度指数（cepci_index_series 表，P6-2 G-03 前置 gate 引入）。

    业务：

    - ``year`` 年份 UNIQUE（如 2018~2024）；
    - ``cepci_value`` Chemical Engineering Plant Cost Index 年度指数值
      （2018=599.0 / 2024=约 800 区间）；COST_EST 模块按 ``year`` 匹配做
      费用时序调整（cost = base_cost * (cepci_year / cepci_base)）。
    - ``source`` 数据来源标记；开发阶段填 ``SYNTHETIC_TEST_DATA``，工艺
      工程师用 Chemical Engineering 杂志真实数据替换后改填具体期号
      （如 ``Chemical Engineering Magazine 2024-Q4``）。
    - ``confirmed_by`` + ``confirmed_at`` 工艺室确认签字（占位字段，正式
      工艺室签字日期填入后 source 字段同步更新）；占位文档见
      ``docs/p6-gate-reports/gate-03-cepci-confirmation.md``。

    不继承 ``TimestampMixin``（元数据表不需 created_by/updated_at 业务
    审计）；改用 created_at/updated_at 直列 + server_default，便于运维
    直接 SQL 排查。
    """

    __tablename__ = "cepci_index_series"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="BIGINT 自增主键",
    )
    year: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True,
        comment="年份（UNIQUE 索引）；如 2018~2024",
    )
    cepci_value: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="CEPCI 年度指数值；COST_EST 按 year 匹配做费用时序调整",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "Chemical Engineering Magazine 2024-Q4"',
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="工艺室确认签字人（占位 NULL，工艺室签字后填入）",
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )


class CoolingTowerCurves(Base):
    """冷却塔特性曲线系数（cooling_tower_curves 表，P6-3 G-04 前置 gate 引入）。

    业务（P6 SPEC §3.2.4.2 CTI ATC-105 KaV/L 方程）：

    - ``tower_model`` 厂商型号（如 ``CTI-ATC105-MARLEY-STD``）；
    - ``curve_source`` 数据来源分类 ``'CTI'`` / ``'MANUFACTURER'``；
    - ``c_coefficient`` / ``m_exponent`` CTI ATC-105 特性曲线系数
      ``KaV/L = C × (L/G)^(−m)``；OPEN_CHANNEL 模块按 ``tower_model`` 匹
      配做 Merkel 冷却塔数值计算（Task 24 ``calc_tower_curve_kav_l``）；
    - ``l_g_ratio_min`` / ``l_g_ratio_max`` 适用 L/G 比区间（NULL 表示
      厂商全区间覆盖）；
    - ``notes`` 备注；
    - ``source`` 数据来源标记；开发阶段填 ``SYNTHETIC_TEST_DATA``，
      工艺工程师用 CTI ATC-105 ED7 真实参数替换后改填具体期号；
    - ``confirmed_by`` + ``confirmed_at`` 工艺室确认签字（占位字段）。
      录入时 upsert 不覆盖这两个字段（mirror CepciIndexSeries 行为）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``(tower_model, source)`` —— 同型号不同数据来源版本可并存。
    """

    __tablename__ = "cooling_tower_curves"

    curve_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键",
    )
    tower_model: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='厂商型号（如 "CTI-ATC105-MARLEY-STD"）',
    )
    curve_source: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment='数据来源分类："CTI" / "MANUFACTURER"',
    )
    c_coefficient: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="CTI ATC-105 特性曲线 C 系数（KaV/L = C × (L/G)^(−m)）",
    )
    m_exponent: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="CTI ATC-105 特性曲线 m 指数",
    )
    l_g_ratio_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="适用 L/G 比下限（NULL=厂商全区间）",
    )
    l_g_ratio_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="适用 L/G 比上限（NULL=厂商全区间）",
    )
    notes: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="备注",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "CTI_ATC-105-ED7"',
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="工艺室确认签字人（占位 NULL，工艺室签字后填入）",
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )
    __table_args__ = (
        UniqueConstraint(
            "tower_model", "source",
            name="uq_cooling_tower_curves_model_source",
        ),
    )


class FiltrationMediaLibrary(Base):
    """过滤介质物性（filtration_media_library 表，P6-3 G-05 前置 gate 引入）。

    业务（P6 SPEC §3.2.7 Ruth 恒压/恒速过滤 + Ergun 深层过滤）：

    - ``medium_type`` 介质大类 ``'SAND'`` / ``'ANTHRACITE'`` / ``'CARBON'``
      / ``'RUTH_FILTER_CLOTH'`` / ``'ERGUN_PACKING'``；
    - ``grade`` 牌号/规格（如 ``'#20-30'`` / ``'A-2010'`` / ``'F-400'``）；
    - ``nominal_rating_um`` 标称过滤精度（μm）；
    - Ruth 滤饼过滤参数（恒压过滤专用）：
      - ``cake_resistance_alpha`` 滤饼比阻（m/kg）；
      - ``specific_resistance_r0`` 单位阻力（1/m）；
    - Ergun 深层过滤参数：
      - ``permeability_k`` 渗透率（m²）；
      - ``porosity_eps`` 孔隙率（0~1）；
    - ``max_temp_c`` 最高使用温度（℃）；
    - ``source`` / ``confirmed_by`` / ``confirmed_at`` 同上。
      录入时 upsert 不覆盖 confirmed 字段。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``(medium_type, grade)``。
    """

    __tablename__ = "filtration_media_library"

    media_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键",
    )
    medium_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment='介质大类："SAND"/"ANTHRACITE"/"CARBON"/"RUTH_FILTER_CLOTH"/"ERGUN_PACKING"',
    )
    grade: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment='牌号/规格（如 "#20-30"/"F-400"）',
    )
    nominal_rating_um: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="标称过滤精度（μm）",
    )
    cake_resistance_alpha: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Ruth 滤饼比阻（m/kg，恒压过滤专用）",
    )
    specific_resistance_r0: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Ruth 单位阻力（1/m，恒压过滤专用）",
    )
    permeability_k: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Ergun 渗透率（m²）",
    )
    porosity_eps: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Ergun 孔隙率（0~1）",
    )
    max_temp_c: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="最高使用温度（℃）",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填厂商 datasheet 名称',
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="工艺室确认签字人（占位 NULL，工艺室签字后填入）",
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )
    __table_args__ = (
        UniqueConstraint(
            "medium_type", "grade",
            name="uq_filtration_media_type_grade",
        ),
    )


class FlareRadiationLimits(Base):
    """火炬地面辐射热通量 BEDD 限值（flare_radiation_limits 表，P6-3 G-06 引入）。

    业务（P6 SPEC §3.2.3.5 + API 521 §7.4.2.3）：

    - ``limit_type`` 限值类型 ``'PROPERTY_LINE'``（财产线）/ ``'PERSONNEL'``
      （人员持续暴露）/ ``'EMERGENCY'``（紧急疏散）三档；Task 22
      ``radiation_check`` 当前硬编码 4.73 / 6.31 / 12.6 kW/m²，本表入库
      后可在后续批联动重构为 DB 读取；
    - ``q_kw_m2_limit`` 允许辐射热通量（kW/m²）；
    - ``distance_m`` / ``effective_height_m`` 对应距离与默认适用高度
      （NULL=不限）；
    - ``notes`` 备注；
    - ``source`` 数据来源；本任务录入即用 API 521 真实公开限值
      （非合成），``source`` 直接填 ``'API521_§7.4.2.3'``，由工艺室
      签字确认。
    - ``confirmed_by`` / ``confirmed_at`` 同上。
      录入时 upsert 不覆盖 confirmed 字段。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``limit_type``。
    """

    __tablename__ = "flare_radiation_limits"

    limit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
        comment="UUID 主键",
    )
    limit_type: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment='限值类型："PROPERTY_LINE"/"PERSONNEL"/"EMERGENCY"',
    )
    q_kw_m2_limit: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="允许辐射热通量（kW/m²）；BEDD 三档 4.73/6.31/12.6",
    )
    distance_m: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="对应距离（m，NULL=不限）",
    )
    effective_height_m: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="默认适用火炬有效高度（m，NULL=不限）",
    )
    notes: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="备注",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；本任务填 "API521_§7.4.2.3" 真实公开限值',
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="工艺室确认签字人（占位 NULL，工艺室签字后填入）",
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )
    __table_args__ = (
        UniqueConstraint("limit_type", name="uq_flare_radiation_limits_type"),
    )


class CostCorrelationLibrary(Base):
    """成本关联式库（cost_correlations 表，SPEC §3.2.8 第三项）。

    业务（P6 SPEC §3.2.8）：

    - 设备类型（``equipment_type``）映射到 ``cost = a + b · S^n`` 关联式，
      其中 ``S`` 为规模参数（塔器直径 / 容器容积 / 换热面积 / 流量 /
      压缩机功率 / 管路 L·D）。
    - ``version`` 关联式版本号（如 ``v1``），便于引入新版关联式（如
      新版化工经济数据回归）不影响旧调用。
    - ``coefficient_a`` / ``coefficient_b`` 关联式系数；
    - ``scaling_exponent_n`` 关联式指数 n；
    - ``scale_unit`` 规模参数单位（如 ``D(m)`` / ``V(m³)``）；
    - ``valid_range_low`` / ``valid_range_high`` 规模参数有效区间；
      区间外 ``lookup_cost_correlation`` 抛 422。
    - ``base_currency`` / ``base_year`` 关联式基准币种 + 基准年份
      （CEPCI 调整的参考时点）。
    - ``notes`` 备注（数据来源说明 / 适用条件）。
    - ``created_by`` 录入人 UUID（FK -> ``users.user_id``，工艺工程师签字）。

    计算层入口：本表接入 ``cost_correlation_lookup`` 模块；
    落库执行：本任务 + Task 35 seed 录入 6 设备类型；后续工艺室签字
    流程同 G-03 / G-04 / G-05 / G-06 模式。

    不继承 ``TaggedRecordMixin``/``TimestampMixin``（元数据表非业务
    计算记录；改用 created_at 直列 + server_default，便于运维 SQL 排查）。

    唯一约束：``(equipment_type, version)``；CHECK 约束：``n`` 范围
    ``(0, 1.5]`` + ``coefficient_b >= 0``（避免非法负系数）。
    """

    __tablename__ = "cost_correlations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="自增主键",
    )
    equipment_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment='设备类型："TOWER"/"VESSEL"/"HEAT_EXCHANGER"/'
                '"PUMP"/"COMPRESSOR"/"PIPING"',
    )
    version: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="v1",
        comment="关联式版本号（默认 v1）",
    )
    coefficient_a: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False,
        comment="关联式系数 a（基准货币）",
    )
    coefficient_b: Mapped[float] = mapped_column(
        Numeric(18, 2), nullable=False,
        comment="关联式系数 b（基准货币）",
    )
    scaling_exponent_n: Mapped[float] = mapped_column(
        Numeric(6, 4), nullable=False,
        comment="关联式指数 n（0 < n <= 1.5）",
    )
    scale_unit: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment='规模参数单位：如 "D(m)" / "V(m³)" / "A(m²)" 等',
    )
    valid_range_low: Mapped[float] = mapped_column(
        Numeric(12, 4), nullable=False,
        comment="规模参数有效区间下界（含）",
    )
    valid_range_high: Mapped[float] = mapped_column(
        Numeric(12, 4), nullable=False,
        comment="规模参数有效区间上界（含）",
    )
    base_currency: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="USD",
        comment='基准货币（默认 USD）',
    )
    base_year: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="2019",
        comment="基准年份（默认 2019，对齐 CEPCI 录入 2018~2024 系列）",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="备注（数据来源 / 适用条件）",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.user_id"), nullable=True,
        comment="录入人（FK -> users.user_id）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )
    __table_args__ = (
        UniqueConstraint(
            "equipment_type", "version",
            name="uq_cost_corr_type_version",
        ),
        CheckConstraint(
            "scaling_exponent_n > 0 AND scaling_exponent_n <= 1.5",
            name="chk_cost_corr_n",
        ),
        CheckConstraint(
            "coefficient_b >= 0",
            name="chk_cost_corr_b_nonneg",
        ),
    )
