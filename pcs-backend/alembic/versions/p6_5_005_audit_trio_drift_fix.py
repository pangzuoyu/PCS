"""P6-5 CI-P6-5-SEED 收口：审计三件套 drift 矫正（5 表 × 3 列).

背景（2026-09-26 pcs_test 对齐后暴露）：

- ORM ``RecordMixin``（app/models/mixins.py）在全部 ~20 张记录表上映射
  P4-0-1 审计三件套（``stale_resolution_path`` / ``hash_changed`` /
  ``changed_fields``）。
- 历史迁移只覆盖了一部分表：
  - ``p4_calc_audit_fields`` 仅 5 表（streams / piping_results / pump_results
    / flash_results / pipe_network_results）；
  - ``p5_open_005`` 及 P6-2+ 新建表在 create_table 里自带三件套。
- 遗漏 5 张 P4 前创建的旧表：``heat_results`` / ``vessel_results`` /
  ``cv_results`` / ``restriction_results`` / ``equipment_list`` ——
  ORM INSERT 含三件套列而真 PG 无列 → 真库写入必炸
  （G-07 heat aggregator 真库用例即因此失败；API 测试跑 sqlite ORM
  metadata 建表故未暴露）。

矫正方式（沿 P6-OPEN-009 psv_results 补列先例，ticket 091500e）：
5 表各 ADD 3 列 nullable，类型对齐 RecordMixin 定义。

应用范围：pcs_test（CI-P6-5-SEED）+ pcs 开发库（迁移链推进到 head 时）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p6_5_005_audit_trio_drift_fix"
down_revision = "p6_5_004_hammerschmidt_K"
branch_labels = None
depends_on = None

# P4 前创建、未进 p4_calc_audit_fields 5 表清单、也未在后续 create_table
# 中带上三件套的 RecordMixin/TaggedRecordMixin 表
_DRIFT_TABLES: tuple[str, ...] = (
    "heat_results",
    "vessel_results",
    "cv_results",
    "restriction_results",
    "equipment_list",
)


def upgrade() -> None:
    """5 张 drift 表各加 P4-0-1 审计三件套（nullable，对齐 RecordMixin）."""
    for table in _DRIFT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "stale_resolution_path",
                sa.String(length=30),
                nullable=True,
                comment="STALE 后走的重算路径（CIA 审计）",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "hash_changed",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("false"),
                comment="record_hash 相对上版是否实质变化",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "changed_fields",
                JSONB(astext_type=sa.Text()),
                nullable=True,
                comment="实质变化字段清单（6 位规范化后仍发散的字段）",
            ),
        )


def downgrade() -> None:
    """5 张 drift 表删审计三件套（与 upgrade 互逆）."""
    for table in _DRIFT_TABLES:
        op.drop_column(table, "changed_fields")
        op.drop_column(table, "hash_changed")
        op.drop_column(table, "stale_resolution_path")
