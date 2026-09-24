"""成本指数 / 元数据型 CONFIG 表（与 config_domain 的业务配置域区分）。

包含 CEPCI（Chemical Engineering Plant Cost Index）年度指数等成本/物价类
元数据，被 COST_EST 模块（P6-3）读取做费用估算。此类表是「元数据」而非
业务计算记录，故不继承 TaggedRecordMixin/record_hash（P6 计划 Task 17）。

如需新增同类型元数据 CONFIG 表（汇率 / 区域人工时薪 / 设备价指数等），
按统一模式追加到本文件即可。
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
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
