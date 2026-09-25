"""P6-2 G-03：CEPCI 年度指数 CONFIG 表（cepci_index_series）+ 唯一索引。

按 P6 计划 §Task 17 硬性前置 gate G-03：

- 新增 ``cepci_index_series`` 表（CONFIG 元数据，非业务计算记录，故不
  含 record_hash / sign_status / project_id / workspace_id）。
- ``year`` 列 UNIQUE 索引 ix_cepci_year（COST_EST 模块按 year 匹配）。
- 录入操作由 ``scripts/p6_2_gate_03_cepci_seed.py`` 单独执行（upsert），
  本迁移只负责 DDL。

DOWN-REVISION = p6_1_c07_cv_standard_profile_code_16（P6-1 末态 alembic
head；2026-09-24 由 C-07 提交）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_2_gate_03_cepci_seed"
down_revision = "p6_1_c07_cv_standard_profile_code_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 cepci_index_series 表 + ix_cepci_year 唯一索引。

    字段定义严格对齐 ``app/models/config.py:CepciIndexSeries`` ORM：

    1. id BIGINT 自增 PK
    2. year INT NOT NULL（uq 索引在 ix_cepci_year 上声明）
    3. cepci_value FLOAT NOT NULL
    4. source VARCHAR(64) NOT NULL（开发期 SYNTHETIC_TEST_DATA）
    5. confirmed_by VARCHAR(64) NULL（工艺室签字占位）
    6. confirmed_at TIMESTAMPTZ NULL（工艺室签字时间占位）
    7. created_at TIMESTAMPTZ server_default=now()
    8. updated_at TIMESTAMPTZ onupdate=now()（通过 DDL 触发器在 ORM 层
       处理；alembic 仅声明列，由 ORM onupdate=func.now() 在写入时刷新）
    """
    op.create_table(
        "cepci_index_series",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True,
                  comment="BIGINT 自增主键"),
        sa.Column("year", sa.Integer(), nullable=False,
                  comment="年份（UNIQUE）；如 2018~2024"),
        sa.Column("cepci_value", sa.Float(), nullable=False,
                  comment="CEPCI 年度指数值；COST_EST 按 year 匹配"),
        sa.Column("source", sa.String(length=64), nullable=False,
                  comment='数据来源；SYNTHETIC_TEST_DATA 或 "Chemical Engineering Magazine 2024-Q4"',  # noqa: E501
                  ),
        sa.Column("confirmed_by", sa.String(length=64), nullable=True,
                  comment="工艺室确认签字人（占位 NULL）"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True,
                  comment="工艺室确认签字时间（占位 NULL）"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False,
                  comment="记录创建时间（DB server_default）"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  comment="记录更新时间（ORM onupdate 触发）"),
    )
    op.create_index(
        "ix_cepci_year",
        "cepci_index_series",
        ["year"],
        unique=True,
    )


def downgrade() -> None:
    """逆序删除：先 drop index 再 drop table（FK 引用顺序与 upgrade 反向）。

    当前表无外键引用，downgrade 仅做 DDL 逆序即可。
    """
    op.drop_index("ix_cepci_year", table_name="cepci_index_series")
    op.drop_table("cepci_index_series")
