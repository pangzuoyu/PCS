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
    Index,
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
    # DB 里 year 的唯一性由自定义命名的唯一索引 ix_cepci_year 承担（不是
    # 命名约定里的 uq_cepci_index_series_year）。ORM 逐字对齐 DB：既不写
    # unique=True（会生成约定名约束），也不写 index=True（会多出
    # ix_cepci_index_series_year 造成 add_index 漂移）。
    __table_args__ = (Index("ix_cepci_year", "year", unique=True),)

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="BIGINT 自增主键",
    )
    year: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="年份（UNIQUE，见 __table_args__ 的 ix_cepci_year）；如 2018~2024",
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


class CompoundHeatingValues(Base):
    """化合物热值库（compound_heating_values 表，P6-4 G-08 前置 gate 引入）。

    业务（P6 SPEC §3.2.3.6 + GPSA Engineering Data Book FIG. 23-2）：

    - ``cas`` CAS 注册号（UNIQUE 索引；如 ``74-82-8``=甲烷）；
    - ``name`` 物质名（如 ``methane`` / ``H2S`` / ``n-butane``）；
    - ``hhv_mj_kg`` 高位热值（MJ/kg，liquid H2O 生成条件）；
    - ``lhv_mj_kg`` 低位热值（MJ/kg，gaseous H2O 生成条件）；
    - ``mw_g_mol`` 分子量（g/mol；用于组分加权计算）；
    - ``source`` 数据来源；开发填 ``SYNTHETIC_TEST_DATA``，工艺工程师用
      GPSA FIG. 23-2 真实数据替换后改填期号（如 ``GPSA_ED13_FIG23-2``）；
    - ``confirmed_by`` + ``confirmed_at`` 工艺室确认签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）；改用
    created_at/updated_at 直列 + server_default，便于运维 SQL 排查。

    唯一约束：``cas``（CAS 注册号全球唯一）。
    """

    __tablename__ = "compound_heating_values"
    # 迁移建的索引名是 ix_compound_heating_values_hhv（列名 hhv_mj_kg 的缩写
    # hhv），非 SQLAlchemy 默认的 ix_compound_heating_values_hhv_mj_kg，故显式声明。
    __table_args__ = (Index("ix_compound_heating_values_hhv", "hhv_mj_kg"),)

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    cas: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True,
        comment="CAS 注册号（UNIQUE 索引 uq_compound_heating_values_cas）；如 '74-82-8' = methane",
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="物质名（如 'methane' / 'H2S' / 'n-butane'）",
    )
    hhv_mj_kg: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="高位热值 HHV（MJ/kg；liquid H2O 生成条件）",
    )
    lhv_mj_kg: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="低位热值 LHV（MJ/kg；gaseous H2O 生成条件）",
    )
    mw_g_mol: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="分子量（g/mol；用于组分加权计算）",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "GPSA_ED13_FIG23-2"',
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


class CompoundPasquillSigma(Base):
    """Pasquill-Gifford σ 参数（Briggs 1973；C-22 扩散用）。

    业务（P6 SPEC §3.10.2 + Briggs 1973）：

    - ``stability_class`` 稳定度等级 UNIQUE A/B/C/D/E/F 6 类；
    - ``a_y`` / ``b_y`` Briggs 横向扩散系数 σ_y = a_y·x·sqrt(1/(1+b_y·x))；
    - ``a_z`` / ``b_z`` Briggs 垂向扩散系数 σ_z = a_z·x·sqrt(1/(1+b_z·x))；
    - 6 行 A~F（Briggs 1973 城市/开阔地形经验系数）。
    - ``source`` 数据来源；开发填 ``SYNTHETIC_TEST_DATA``，工艺工程师用
      Briggs 1973 真实期号替换后改填具体期号；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
    """

    __tablename__ = "compound_pasquill_sigma"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    stability_class: Mapped[str] = mapped_column(
        String(1), nullable=False, unique=True,
        comment='Pasquill-Gifford 稳定度等级 UNIQUE：A/B/C/D/E/F',
    )
    a_y: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Briggs 横向扩散系数 a_y（σ_y = a_y·x·sqrt(1/(1+b_y·x))）",
    )
    b_y: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Briggs 横向扩散系数 b_y",
    )
    a_z: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Briggs 垂向扩散系数 a_z（σ_z = a_z·x·sqrt(1/(1+b_z·x))）",
    )
    b_z: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Briggs 垂向扩散系数 b_z",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "Briggs_1973_open_terrain"',
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


class CompoundApi521Thresholds(Base):
    """API 521 §5.15 辐射热通量阈值（C-22 致死/致伤用）。

    业务（P6 SPEC §3.10.2 + API 521 §5.15 Table 5-15）：

    - ``threshold_type`` 阈值类型 UNIQUE；如 ``INJURY``（4.7 kW/m² 致伤）
      / ``LETHALITY``（12.6 kW/m² 致死）；
    - ``flux_kw_m2`` 允许辐射热通量（kW/m²）；
    - 2 行（INJURY/LETHALITY）。
    - ``source`` 数据来源；开发填 ``SYNTHETIC_TEST_DATA``，工艺工程师用
      API 521 真实期号替换后改填具体期号；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
    """

    __tablename__ = "compound_api521_thresholds"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    threshold_type: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True,
        comment='阈值类型 UNIQUE：如 "INJURY"/"LETHALITY"',
    )
    flux_kw_m2: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="允许辐射热通量（kW/m²）；API 521 §5.15 Table 5-15",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "API521_§5.15_Table_5-15"',
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


class CompoundIso9613AtmosphericAbsorption(Base):
    """ISO 9613-2 大气吸收系数（C-23 噪声用）。

    业务（P6 SPEC §3.10.3 + ISO 9613-2）：

    - ``temperature_c`` 温度（°C）+ ``humidity_pct`` 相对湿度（% RH）联合 UNIQUE；
    - ``alpha_db_km`` 大气吸收系数 A（dB/km）；
    - 4 行（10/15/20/25°C × 50% RH，标准工况）。
    - ``source`` 数据来源；开发填 ``SYNTHETIC_TEST_DATA``，工艺工程师用
      ISO 9613-2 真实期号替换后改填具体期号；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``(temperature_c, humidity_pct)``。
    """

    __tablename__ = "compound_iso9613_atmospheric_absorption"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    temperature_c: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="温度（°C；与 humidity_pct 联合 UNIQUE）",
    )
    humidity_pct: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="相对湿度（% RH；与 temperature_c 联合 UNIQUE）",
    )
    alpha_db_km: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="大气吸收系数 A（dB/km；ISO 9613-2）",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "ISO9613-2_§7"',
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
            "temperature_c", "humidity_pct",
            name="uq_compound_iso9613_temp_humidity",
        ),
    )


class PipeEModulus(Base):
    """管材弹性模量 E（pipe_e_modulus 表，P6-6B T3 引入；C-13 Joukowsky 用）。

    业务（P6 SPEC §3.2.3 V1.8 + API 5L (2018) / ASTM A106 / ASTM A335）：

    - ``grade`` 管材等级 UNIQUE（如 API 5L ``X42/X52/X65/X70/X80`` +
      ASTM A106 ``A106-B`` + ASTM A335 ``A335-P11/A335-P22``）；
    - ``e_psi`` 弹性模量 E（psi，典型值 70°F；30,000,000 psi = 206.84 GPa）；
    - ``spec_source`` 标准来源（``API 5L`` / ``ASTM A106`` / ``ASTM A335``）；
    - ``source`` 数据来源；本批录入即用 API 5L (2018) + ASTM A106/A335
      真实公开值（非合成），``source`` 直接填
      ``'API 5L (2018) + ASTM A106/A335'``；由工艺工程师签字确认；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一约束：``grade``（管材等级唯一）。
    """

    __tablename__ = "pipe_e_modulus"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    grade: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        comment='管材等级 UNIQUE：API 5L "X42/X52/X65/X70/X80" / '
                'ASTM A106 "A106-B" / ASTM A335 "A335-P11/A335-P22"',
    )
    e_psi: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment=(
            "弹性模量 E（psi；典型值 70°F）；Wylie-Streeter 含管壁修正用"
        ),
    )
    spec_source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='标准来源："API 5L" / "ASTM A106" / "ASTM A335"',
    )
    source: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment='数据来源；本批填 "API 5L (2018) + ASTM A106/A335" 真实公开值',
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="工艺室确认签字人",
    )
    confirmed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（DB onupdate 触发）",
    )


class CompoundHammerschmidtK(Base):
    """Hammerschmidt K 因子（C-18 水合物抑制用）。

    业务（P6 SPEC §3.9.4 + Hammerschmidt 1934）：

    - ``inhibitor_type`` 抑制剂类型 UNIQUE：MEOH / EG / DEG / TEG / NACL；
    - ``K`` 温降常数（无量纲；Hammerschmidt 1934 Eq: ΔT = K·X / (M·(1-X))）；
    - 5 行（MEOH=2335 / EG=2220 / DEG=2335 / TEG=2500 / NACL=1297）。
    - ``source`` 数据来源；开发填 ``SYNTHETIC_TEST_DATA``，工艺工程师用
      Hammerschmidt 1934 真实期号替换后改填具体期号；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
    """

    __tablename__ = "compound_hammerschmidt_K"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    inhibitor_type: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True,
        comment='抑制剂类型 UNIQUE：MEOH/EG/DEG/TEG/NACL',
    )
    K: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Hammerschmidt K 因子（无量纲；ΔT = K·X / (M·(1-X))）",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                '真实数据填如 "Hammerschmidt_1934"',
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


class CompoundDeltaHVapNaturalGas(Base):
    """ΔH_vap 蒸发潜热（natural gas 路径，PSV C-21 fire case）。

    业务（P6 SPEC §3.5.2 + Ruling 9 双 surface + OPEN-P6-6A-5）：

    - ``convention`` UNIQUE（口径标识）；两行：
      - ``TYPICAL_2260``：GPSA §3.4 typical natural gas ΔH_vap = 2260 kJ/kg
        （向后兼容默认口径，OPEN-P6-6A-5 Ruling 14 back-compat）；
      - ``XLS_CONVENTION_208``：XLS PR-025 隐式 ΔH_vap = 208 kJ/kg（liquefied
        natural gas 口径；OPEN-P6-6A-5 Ruling 9/14 关闭此 OPEN 项）。
    - ``dh_vap_kj_kg`` ΔH_vap 数值（kJ/kg）；
    - ``notes`` 工程备注；
    - ``source`` 数据来源；本批录 GPSA common 公开典型值
      （2260 = GPSA §3.4 typical；208 = XLS PR-025 implicit），由工艺室
      签字确认；``source`` 填 ``'GPSA §3.4 typical + XLS PR-025 implicit'``。
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``convention``。
    """

    __tablename__ = "compound_delta_h_vap_natural_gas"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    convention: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True,
        comment='口径标识 UNIQUE："TYPICAL_2260" / "XLS_CONVENTION_208"',
    )
    dh_vap_kj_kg: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="ΔH_vap 蒸发潜热（kJ/kg；GPSA §3.4 / XLS PR-025 implicit）",
    )
    notes: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="工程备注（GPSA / XLS 隐式口径溯源）",
    )
    source: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment='数据来源；本批填 "GPSA §3.4 typical + XLS PR-025 implicit"',
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='本批填 "P6-6B_ENG_TEAM"；工艺工程师二次核对后改填实际签字人',
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，工艺室签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（ORM onupdate 触发）",
    )


class DrainOrificeCdYCr(Base):
    """Drain orifice Cd/Y_cr 流量系数（C-19 排污孔板 OPEN-P6-6A-4 关闭）。

    业务（P6 SPEC §3.7.2 + Ruling 12 + Ruling 13）：

    - ``fluid`` UNIQUE：``NATURAL_GAS`` / ``AIR`` / ``STEAM`` / ``WATER`` /
      ``N2`` / ``CO2``；
    - ``beta_range_min`` / ``beta_range_max`` β 直径比范围（无量纲）；
    - ``cd`` 流量系数（无量纲；XLS PR-023 + Miller 1990 取值）；
    - ``y_cr`` 临界压力比（无量纲；XLS PR-023 + Miller 1990 取值）；
    - ``notes`` 工程备注；
    - ``source`` 数据来源；本批填 ``'XLS PR-023 + Miller (1990) discharge coefficients'``；
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    唯一索引：``fluid``。
    """

    __tablename__ = "drain_orifice_Cd_Y_cr"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    fluid: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True,
        comment='介质 UNIQUE："NATURAL_GAS" / "AIR" / "STEAM" / "WATER" / "N2" / "CO2"',
    )
    beta_range_min: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="β 直径比下限（无量纲；典型 0.0）",
    )
    beta_range_max: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="β 直径比上限（无量纲；典型 0.7）",
    )
    cd: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Cd 流量系数（无量纲；XLS PR-023 + Miller 1990 取值）",
    )
    y_cr: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Y_cr 临界压力比（无量纲；XLS PR-023 + Miller 1990 取值）",
    )
    notes: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="工程备注（XLS PR-023 / Miller 1990 取值溯源）",
    )
    source: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment='数据来源；本批填 "XLS PR-023 + Miller (1990) discharge coefficients"',
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='本批填 "P6-6B_ENG_TEAM"；工艺工程师二次核对后改填实际签字人',
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，工艺室签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（ORM onupdate 触发）",
    )


class GlycolDehydrationFullSystem(Base):
    """C-16 glycol dehydration full system 典型工况范围（P6-6B CONFIG 占位）。

    业务（P6 SPEC §3.9.1 + GPSA Fig. 20-XX + McKetta-Wehe）：

    - ``parameter`` UNIQUE：典型工况参数名（TEG 浓度 / reboiler temperature
      / stripping gas rate / column diameter / column height / NTU /
      reflux ratio / contactor pressure / water removal efficiency /
      reboiler duty）；
    - ``min_value`` 数值最小值；
    - ``max_value`` 数值最大值；
    - ``unit`` 数值单位；
    - ``notes`` 工程备注；
    - 估算 10 行典型工况范围（per GPSA Fig. 20-XX + McKetta-Wehe 公开值）；
    - ``source`` / ``confirmed_by`` / ``confirmed_at`` 字段同其他 CONFIG 表。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
    服务扩展待 P6-7。
    """

    __tablename__ = "glycol_dehydration_full_system"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    parameter: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True,
        comment="典型工况参数 UNIQUE：teg_concentration / reboiler_temperature 等",
    )
    min_value: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="数值最小值",
    )
    max_value: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="数值最大值",
    )
    unit: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="数值单位（wt% / °F / scf/gal TEG / ft / NTU / - / psia / % / kBtu/hr）",
    )
    notes: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
        comment="工程备注（典型工况语境）",
    )
    source: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment='数据来源；本批填 "GPSA Fig. 20-XX + McKetta-Wehe '
                '(TBD engineer verify)"',
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment='本批填 "P6-6B_ENG_TEAM_TBD"；工艺工程师二次核对后改填实际签字人',
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，工艺室签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（ORM onupdate 触发）",
    )


class ConfigEnergyConversionFactor(Base):
    """折标油 / 折标煤系数（P7 Sprint 2 T0 / 综合能耗汇总 CONFIG 元数据）。

    业务（P7 SPEC V1.4 §3.2.2（5）+ §4.6 + P7-OPEN-009 §6.3 + 三层标准
    GB/T 2589-2020 + GB 30251-2024 + GB/T 50441-2016）：

    - R1 修订（PCS-SIGN-F-P0-001-2026-10-08-R1）：从单行/类拆为多行/类
      - 电：2 行（当量值 EQUIVALENT / 等价值 EQUIVALENT_VALUE）
      - 蒸汽：9 行（按 pressure_level 9 档）
      - 水：9 行（按 water_type 9 类）
      - 燃料气：3 行（按 sub_type 油田气/气田气/炼厂燃料气）
      - 仪表空气：2 行（按 sub_type 净化/非净化）
      - 氮气：1 行
    - 复合 UNIQUE (energy_type, value_type, sub_type, pressure_level, water_type)
    - ``toe_factor`` 折标油系数（kg 标油 / 单位消耗量）。**单位口径明确**：
      电 = kWh，燃料气 = Nm³，**蒸汽 = 吨**，**水 = 吨**，气体 = m³，
      低温余热 = GJ。蒸汽/水 toe_factor 是 **per-tonne**（与 GB 30251-2024 附录 A
      工艺室 2026-10-08 签齐一致），service 端 ``consumption × toe_factor``
      直接乘以吨数得到 kg 标油。
    - ``standard_coal_factor`` 折标煤系数（kg 标煤 / 单位消耗量；同 toe_factor
      单位口径）；
    - ``source`` 数据来源；GB 30251-2024 附录A + GB/T 2589-2020 + GB/T 50441-2016
    - ``confirmed_by`` / ``confirmed_at`` 工艺室签字（占位字段）。

    不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。

    复合索引：``energy_type`` + value_type/sub_type/pressure_level/water_type。
    """

    __tablename__ = "config_energy_conversion_factors"
    __table_args__ = (
        # bug-137 fix: PostgreSQL 的 UNIQUE 遇 NULL 失效 (NULL 互不相等),
        # 4 个分类列里任意一个为 NULL 时重复行照样能插 —— 实测插出 7 行重复。
        # PG 15+ 用 NULLS NOT DISTINCT 表达「NULL 也算相等」的语义。
        # 本机 PG 18.6 支持; SQLite 侧 SQLAlchemy 自动降级为普通 UNIQUE
        # (与迁移前行为一致, 不更差)。
        UniqueConstraint(
            "energy_type", "value_type", "sub_type",
            "pressure_level", "water_type",
            name="uq_config_energy_conversion_factors_classification",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
        comment="BIGINT 自增主键",
    )
    energy_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment=(
            "能源类型：ELECTRICITY/FUEL_GAS/STEAM/WATER/GAS/LOW_TEMP_HEAT/NITROGEN/"
            "INSTRUMENT_AIR"
        ),
    )
    value_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "电当量/等价值 (GB 30251-2024 §6.1.1): "
            "ELECTRICITY: EQUIVALENT / EQUIVALENT_VALUE; 其他能源: NULL"
        ),
    )
    sub_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "子类（按能源类型不同）: "
            "FUEL_GAS: OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS; "
            "INSTRUMENT_AIR: PURIFIED/NON_PURIFIED"
        ),
    )
    pressure_level: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "蒸汽压力等级 (GB 30251-2024 附录A 9 档): "
            "GE_7_0_MPA / 4_5_TO_7_0_MPA / 3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / "
            "1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / 0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / "
            "LT_0_3_MPA"
        ),
    )
    water_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment=(
            "水类型 (GB 30251-2024 附录A 9 类): "
            "FRESH_WATER / CIRCULATING_WATER / SOFTENED_WATER / DEMINERALIZED_WATER / "
            "LP_DEAERATED_WATER / HP_DEAERATED_WATER / TURBINE_CONDENSATE / "
            "120C_CONDENSATE_TREATED / 120C_CONDENSATE_REUSABLE"
        ),
    )
    toe_factor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment=(
            "折标油系数（kg 标油/单位消耗量；"
            "电 kWh/燃料 m³/蒸汽 t/水 t/氮气 m³/仪表空气 m³）"
        ),
    )
    standard_coal_factor: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="折标煤系数（kg 标煤 / 单位消耗量；同 toe_factor 单位口径）",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment=(
            '数据来源；GB_30251_2024_APPENDIX_A + '
            'GB_T_2589_2020_APPENDIX_A + GB_T_50441_2016_APPENDIX'
        ),
    )
    confirmed_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="工艺室确认签字人（占位 NULL，工艺室 R1 签署后填入）",
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="工艺室确认签字时间（占位 NULL，R1 签字后填入）",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        comment="记录创建时间（DB server_default）",
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(),
        comment="记录更新时间（ORM onupdate 触发）",
    )
