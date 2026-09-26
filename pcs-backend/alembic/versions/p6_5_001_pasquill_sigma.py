"""P6-5 compound_pasquill_sigma CONFIG 表（C-22 Pasquill-Gifford 扩散 / SPEC §3.10.2）。

依据：

- P6-5 计划 Task C5 收口（4 张 CONFIG 表 + 4 alembic + 4 seed）。
- 镜像 P6-4 G-08 模式（commit 134e26b Task 5 / p6_4_001）。
- Briggs 1973 Pasquill-Gifford 6 类稳定度（A/B/C/D/E/F）。

设计要点：

- 单张 CONFIG 元数据表（``compound_pasquill_sigma``），存 6 行 Pasquill
  稳定度的 Briggs 1973 系数 (a_y, b_y, a_z, b_z)。
- 字段定义严格对齐 ``app/models/config.py:CompoundPasquillSigma`` ORM
  class。
- 不继承 ``TaggedRecordMixin``（元数据表非业务计算记录）。
- 录入操作由 ``scripts/p6_5_seed_pasquill_sigma.py`` 单独执行；本迁移
  只负责 DDL。

DOWN-REVISION = ``p6_4_004_psychro_saturation_w_fields``（P6-4 末态
alembic head；2026-09-25 由 Task 5 提交）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_5_001_pasquill_sigma"
down_revision = "p6_4_004_psychro_saturation_w_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 ``compound_pasquill_sigma`` 表（C-22 Pasquill-Gifford 扩散）。

    字段定义严格对齐 ``app/models/config.py:CompoundPasquillSigma``。
    """
    op.create_table(
        "compound_pasquill_sigma",
        sa.Column(
            "id", sa.Integer(),
            primary_key=True, autoincrement=True,
            comment="BIGINT 自增主键",
        ),
        sa.Column(
            "stability_class", sa.String(length=1), nullable=False,
            comment="Pasquill-Gifford 稳定度等级 UNIQUE：A/B/C/D/E/F",
        ),
        sa.Column(
            "a_y", sa.Float(), nullable=False,
            comment="Briggs 横向扩散系数 a_y",
        ),
        sa.Column(
            "b_y", sa.Float(), nullable=False,
            comment="Briggs 横向扩散系数 b_y",
        ),
        sa.Column(
            "a_z", sa.Float(), nullable=False,
            comment="Briggs 垂向扩散系数 a_z",
        ),
        sa.Column(
            "b_z", sa.Float(), nullable=False,
            comment="Briggs 垂向扩散系数 b_z",
        ),
        sa.Column(
            "source", sa.String(length=64), nullable=False,
            comment='数据来源；开发填 "SYNTHETIC_TEST_DATA"，'
                    '真实数据填如 "Briggs_1973_open_terrain"',
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
            "stability_class",
            name="uq_compound_pasquill_sigma_stability_class",
        ),
    )


def downgrade() -> None:
    """删除 ``compound_pasquill_sigma`` 表（C5 测试 / 回滚用）。"""
    op.drop_table("compound_pasquill_sigma")
