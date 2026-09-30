"""P6-5 compound_hammerschmidt_K CONFIG 表（C-18 Hammerschmidt K 因子).

依据：

- P6-5 计划 Task C5 收口（4 张 CONFIG 表 + 4 alembic + 4 seed）。
- 镜像 p6_5_001/002/003 模式。
- Hammerschmidt 1934 温降公式 ΔT = K·X / (M·(1-X)) 的 K 因子。

设计要点：

- 单张 CONFIG 元数据表（``compound_hammerschmidt_K``），存 5 行抑制剂的
  K 因子（MEOH=2335 / EG=2220 / DEG=2335 / TEG=2500 / NACL=1297）。
- 字段定义严格对齐 ``app/models/config.py:CompoundHammerschmidtK`` ORM class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_5_seed_hammerschmidt_K.py`` 单独执行；本迁移
  只负责 DDL。

DOWN-REVISION = ``p6_5_003_iso9613_atmospheric_absorption``。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_5_004_hammerschmidt_K"
down_revision = "p6_5_003_iso9613_atmospheric_absorption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_hammerschmidt_K`` 表（C-18 水合物抑制 K 因子).

    字段定义严格对齐 ``app/models/config.py:CompoundHammerschmidtK``。
    """
    op.create_table(
        "compound_hammerschmidt_K",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "inhibitor_type", sa.String(length=32), nullable=False,
            comment="抑制剂类型 UNIQUE：MEOH/EG/DEG/TEG/NACL",
        ),
        sa.Column(
            "K", sa.Float(), nullable=False,
            comment="Hammerschmidt K 因子（无量纲；ΔT = K·X / (M·(1-X))）",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "Hammerschmidt_1934"',
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
            "inhibitor_type",
            name="uq_compound_hammerschmidt_K_inhibitor_type",
        ),
    )


def downgrade() -> None:
    """删除 ``compound_hammerschmidt_K`` 表（C5 测试 / 回滚用）."""
    op.drop_table("compound_hammerschmidt_K")
