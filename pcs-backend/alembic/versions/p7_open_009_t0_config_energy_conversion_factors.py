"""P7 Sprint 2 T0: config_energy_conversion_factors CONFIG 表 (折标煤系数).

依据：

- P7-OPEN-009 §6.3 CONFIG 折标煤系数 seed（P7-REV-02=A 触发）
- GB/T 50441 附录 + 工艺室 2026-10-XX 签署
- P6-5+ 4 张 compound_* CONFIG 表 + 5-min TTL 缓存模式
- P7 SPEC V1.4 §3.2.2（5）综合能耗汇总（utility_energy_summary）依赖此表

设计要点：

- 单张 CONFIG 元数据表（``config_energy_conversion_factors``），存 6 类能源
  折标油 / 折标煤系数：ELECTRICITY / FUEL_GAS / STEAM / WATER / GAS /
  LOW_TEMP_HEAT。
- 字段：source / energy_type（UNIQUE）/ toe_factor（kWh 或 kg → kg 标油）/
  standard_coal_factor（kg 标煤）/ confirmed_by / confirmed_at + 标准 timestamp。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p7_open_009_t0_seed_energy_conversion_factors.py``
  单独执行；本迁移只负责 DDL。

DOWN-REVISION = ``p7_s1_002``。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p7_open_009_t0_config_energy_conversion_factors"
down_revision = "p7_s1_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``config_energy_conversion_factors`` 表（折标煤系数元数据).

    字段定义严格对齐 ``app/models/config.py:ConfigEnergyConversionFactor``。
    """
    op.create_table(
        "config_energy_conversion_factors",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "energy_type", sa.String(length=32), nullable=False,
            comment="能源类型 UNIQUE：ELECTRICITY/FUEL_GAS/STEAM/WATER/GAS/LOW_TEMP_HEAT",
        ),
        sa.Column(
            "toe_factor", sa.Float(), nullable=False,
            comment=(
                "折标油系数（kg 标油/单位消耗量；"
                "电 kWh/燃料 m³/蒸汽 kg/水 kg/气体 m³/低温余热 GJ）"
            ),
        ),
        sa.Column(
            "standard_coal_factor", sa.Float(), nullable=False,
            comment="折标煤系数（kg 标煤 / 单位消耗量；同 toe_factor 单位口径）",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "GB_T_50441_APPENDIX"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL，工艺室 2026-10-15 签署后填入）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL，签字后填入）",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
            comment="记录创建时间（DB server_default）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True,
            comment="记录更新时间（ORM onupdate 触发）",
        ),
        sa.UniqueConstraint(
            "energy_type",
            name="uq_config_energy_conversion_factors_energy_type",
        ),
    )


def downgrade() -> None:
    """删除 ``config_energy_conversion_factors`` 表（T0 测试 / 回滚用）."""
    op.drop_table("config_energy_conversion_factors")
