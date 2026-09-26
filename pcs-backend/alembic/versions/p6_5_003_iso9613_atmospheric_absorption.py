"""P6-5 compound_iso9613_atmospheric_absorption CONFIG 表（C-23 ISO 9613-2 大气吸收）。

依据：

- P6-5 计划 Task C5 收口（4 张 CONFIG 表 + 4 alembic + 4 seed）。
- 镜像 p6_5_001 / p6_5_002 模式。
- ISO 9613-2 大气吸收系数 A（dB/km）随温度/湿度变化。

设计要点：

- 单张 CONFIG 元数据表（``compound_iso9613_atmospheric_absorption``），
  存 4 行标准工况（10/15/20/25°C × 50% RH）。
- 字段定义严格对齐 ``app/models/config.py:CompoundIso9613AtmosphericAbsorption``
  ORM class；联合 UNIQUE（temperature_c, humidity_pct）。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_5_seed_iso9613_atmospheric_absorption.py`` 单独
  执行；本迁移只负责 DDL。

DOWN-REVISION = ``p6_5_002_api521_thresholds``。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_5_003_iso9613_atmospheric_absorption"
down_revision = "p6_5_002_api521_thresholds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_iso9613_atmospheric_absorption`` 表（C-23 大气吸收系数）。

    字段定义严格对齐 ``app/models/config.py:CompoundIso9613AtmosphericAbsorption``。
    """
    op.create_table(
        "compound_iso9613_atmospheric_absorption",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "temperature_c", sa.Float(), nullable=False,
            comment="温度（°C；与 humidity_pct 联合 UNIQUE）",
        ),
        sa.Column(
            "humidity_pct", sa.Float(), nullable=False,
            comment="相对湿度（% RH；与 temperature_c 联合 UNIQUE）",
        ),
        sa.Column(
            "alpha_db_km", sa.Float(), nullable=False,
            comment="大气吸收系数 A（dB/km；ISO 9613-2）",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "ISO9613-2_§7"',
        ),
        sa.Column(
            "confirmed_by", sa.String(length=64), nullable=True,
            comment="工艺室确认签字人（占位 NULL）",
        ),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), nullable=True,
            comment="工艺室确认签字时间（占位 NULL）",
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
            "temperature_c", "humidity_pct",
            name="uq_compound_iso9613_temp_humidity",
        ),
    )


def downgrade() -> None:
    """删除 ``compound_iso9613_atmospheric_absorption`` 表（C5 测试 / 回滚用）。"""
    op.drop_table("compound_iso9613_atmospheric_absorption")
