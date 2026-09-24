"""P6-3 Task 30：3 张结果表迁移 + P6-OPEN-009 修复 + column_sizing design_stage 补列。

依据：
- P6 计划 §Task 30（3 张 P6-3 结果表：open_channel_results / filtration_results /
  cost_est_results）
- ticket 091500e P6-OPEN-009（psv_results alembic drift 缺 3 列：
  stale_resolution_path / hash_changed / changed_fields）
- CAVEAT-1 / SUP-008 §8.4（column_sizing design_stage NOT NULL +
  server_default 'BASIC'）

设计要点：
- 3 张结果表实际由 v3.1 schema migration ``dd47298c9c38_v3_1_full_schema_53_tables``
  提前创建（含 TaggedRecordMixin 字段），本迁移只追加 Task 30 扩展字段（critical_depth
  等派生列），不重 create_table / 不 drop 既有数据。alembic upgrade 在 pcs_test 上的
  实际路径是「追加列」而非「建表」。
- ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` 模式保证幂等：多次跑迁移（CI /
  重复 upgrade）不会因列已存在失败。alembic 版本号仍会前进（revision 标记本次
  migration 落地），但 DDL 是 no-op。
- P6-OPEN-009：psv_results 3 列以 ``ADD COLUMN IF NOT EXISTS`` 追加；同幂等。
- column_sizing.design_stage 已由 P5-OPEN-005（迁移 ``p5_open_005_model_extension``）
  落地，本迁移以 ``ADD COLUMN IF NOT EXISTS`` 验证；DB 已有则 no-op，DB 缺失则补
  NOT NULL + server_default 'BASIC'。

DOWN-REVISION = p6_3_001_three_config_tables（P6-3 Task 29 闭环）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_3_002_open_channel_filtration_cost_results"
down_revision = "p6_3_001_three_config_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """追加 3 张结果表 Task 30 扩展字段 + P6-OPEN-009 psv_results 3 列。

    模式：``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` 幂等；
    pcs_test 上 v3.1 schema migration 已建 3 张结果表（含 mixin 字段），
    本迁移只追加 Task 30 新增派生列。alembic 升级过程记录在本 revision 即可。
    """
    # === 1. open_channel_results（SPEC §3.2.6；Task 31 落库）===
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS critical_depth DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS froude_number DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS manning_n DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS hydraulic_radius DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS jump_type VARCHAR(16)"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS conjugate_depth DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE open_channel_results "
        "ADD COLUMN IF NOT EXISTS energy_loss DOUBLE PRECISION"
    )

    # === 2. filtration_results（SPEC §3.2.7；Task 33/34 落库）===
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS media_type VARCHAR(32)"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS cake_resistance_alpha DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS specific_resistance_r0 DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS permeability_k DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS porosity_eps DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS filter_velocity DOUBLE PRECISION"
    )

    # === 3. cost_est_results（SPEC §3.2.8；Task 35 落库）===
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS base_cost NUMERIC(18, 2)"
    )
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS base_year INTEGER"
    )
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS cepci_index_base DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS cepci_index_target DOUBLE PRECISION"
    )
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS correlation_source VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE cost_est_results "
        "ADD COLUMN IF NOT EXISTS scaling_exponent DOUBLE PRECISION"
    )

    # === 4. P6-OPEN-009 fix：psv_results 补 3 列（审计列护栏）===
    # 迁移与实现见 §审计列护栏 注释：stale_resolution_path / hash_changed /
    # changed_fields 只经 calc_lineage.finalize_calc_record 或 CIA 引擎写，
    # 业务模块禁止直写；本迁移只提供列。
    op.execute(
        "ALTER TABLE psv_results "
        "ADD COLUMN IF NOT EXISTS stale_resolution_path TEXT"
    )
    op.execute(
        "ALTER TABLE psv_results "
        "ADD COLUMN IF NOT EXISTS hash_changed BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE psv_results "
        "ADD COLUMN IF NOT EXISTS changed_fields JSONB"
    )

    # === 5. column_sizing.design_stage（SUP-008 §8.4 OPEN-009 V1.3 落地遗漏补齐）===
    # 注意：实际表名是 ``column_sizing`` 而非 ``column_sizing_results``（P5-OPEN-005
    # 已落地）。ADD COLUMN IF NOT EXISTS 幂等：DB 已有则 no-op，DB 缺失则补
    # NOT NULL + server_default 'BASIC'。
    op.execute(
        "ALTER TABLE column_sizing "
        "ADD COLUMN IF NOT EXISTS design_stage VARCHAR(16) "
        "NOT NULL DEFAULT 'BASIC'"
    )


def downgrade() -> None:
    """逆序删除本迁移添加的列。

    注：3 张结果表（open_channel_results / filtration_results / cost_est_results）
    本迁移未创建（v3.1 schema migration 创建），故不 drop。本迁移仅追加列，
    降级只删本迁移添加的列。
    """
    # 5. column_sizing.design_stage
    op.execute("ALTER TABLE column_sizing DROP COLUMN IF EXISTS design_stage")
    # 4. psv_results 3 列（逆序）
    op.execute("ALTER TABLE psv_results DROP COLUMN IF EXISTS changed_fields")
    op.execute("ALTER TABLE psv_results DROP COLUMN IF EXISTS hash_changed")
    op.execute("ALTER TABLE psv_results DROP COLUMN IF EXISTS stale_resolution_path")
    # 3. cost_est_results 6 列（逆序）
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS scaling_exponent")
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS correlation_source")
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS cepci_index_target")
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS cepci_index_base")
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS base_year")
    op.execute("ALTER TABLE cost_est_results DROP COLUMN IF EXISTS base_cost")
    # 2. filtration_results 6 列（逆序）
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS filter_velocity")
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS porosity_eps")
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS permeability_k")
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS specific_resistance_r0")
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS cake_resistance_alpha")
    op.execute("ALTER TABLE filtration_results DROP COLUMN IF EXISTS media_type")
    # 1. open_channel_results 7 列（逆序）
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS energy_loss")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS conjugate_depth")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS jump_type")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS hydraulic_radius")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS manning_n")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS froude_number")
    op.execute("ALTER TABLE open_channel_results DROP COLUMN IF EXISTS critical_depth")