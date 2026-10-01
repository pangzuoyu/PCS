"""P6-9-PICKUP-4 T1: pcs_test DB schema drift 修复.

依据 P6-9-PICKUP-4 brief（2026-09-30）：9 个 pre-existing pytest failures 中
8 个根因是 pcs_test DB 与迁移声明 schema 不一致（历史 diff）：

1. **design_stage server_default 'BASIC'** — 4 表（pump_results /
   psv_results / vessel_results / column_sizing）迁移声明
   ``server_default='BASIC'::design_stage_enum`` 但 pcs_test 实际
   ``column_default=''``（SUP-008 §8.4 OPEN-009 漏配）
2. **ix_streams_simulation_status + ix_streams_estimated** — p3sim_streams_sim_fields
   迁移声明 create_index，pcs_test 实际不存在索引（SIM-17 §3.2.4 漏配）
3. **ix_compound_heating_values_hhv** — p6_4_001 迁移声明 create_index，
   pcs_test 实际不存在索引；导致 test_reversible_segment_roundtrip downgrade
   抛 ``index does not exist``
4. **uq_equipment_type_codes_project_type** — p1_sprint3_nullable_equipment_type_codes
   迁移声明 UNIQUE(project_id, type_code)，pcs_test 实际只剩 PK（PK 重建后
   UNIQUE 未重建）

DOWN-REVISION = ``p6_9_pickup_3_drop_nielsen_1988_params``（当前 alembic HEAD）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_9_pickup_4_drift_fixes"
down_revision = "p6_9_pickup_3_drop_nielsen_1988_params"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """修复 pcs_test 8 个 DB drift 失败（T1 / 单迁移收口).

    6 段（顺序无关）：
    - A. design_stage server_default 'BASIC'（4 表，sup008 + open_005 漏配）
    - B. ix_streams_simulation_status（streams SIM-17 漏配）
    - C. ix_streams_estimated（streams SIM-17 漏配）
    - D. ix_compound_heating_values_hhv（compound_heating_values P6-4 漏配）
    - E. uq_equipment_type_codes_project_type（equipment_type_codes Sprint3 漏配）
    - F. cepci_index_series_year → ix_cepci_year 重命名
      （p6_2_gate_03_cepci_seed 声明 ix_cepci_year，但 ORM 自动建出
      ix_cepci_index_series_year；round-trip 需迁移声明名才能 drop）

    所有操作幂等（IF NOT EXISTS / IF EXISTS / IF EXISTS），可重复运行。
    """
    # A. design_stage server_default 'BASIC' on 4 表
    for table in (
        "pump_results",
        "psv_results",
        "vessel_results",
        "column_sizing",
    ):
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN design_stage "
            f"SET DEFAULT 'BASIC'::design_stage_enum"
        )

    # B + C. streams SIM-17 索引
    op.create_index(
        "ix_streams_simulation_status",
        "streams",
        ["simulation_status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_streams_estimated",
        "streams",
        ["estimated"],
        if_not_exists=True,
    )

    # D. compound_heating_values hhv 数值索引
    op.create_index(
        "ix_compound_heating_values_hhv",
        "compound_heating_values",
        ["hhv_mj_kg"],
        if_not_exists=True,
    )

    # E. equipment_type_codes 复合 UNIQUE（替代原 PK 的唯一性语义）
    # 幂等：仅在不存在时 ADD（避免 DROP CASCADE 触发 fk_equipment_list_type_code_composite 重建）
    # p1_sprint3_nullable up 阶段已 ADD 此约束，重复运行需 IF NOT EXISTS 守门
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "               WHERE conname = 'uq_equipment_type_codes_project_type') THEN "
        "ALTER TABLE equipment_type_codes "
        "ADD CONSTRAINT uq_equipment_type_codes_project_type "
        "UNIQUE (project_id, type_code); "
        "END IF; "
        "END $$"
    )

    # F. cepci_index_series_year → ix_cepci_year 重命名（round-trip 兼容）
    # 仅在 ORM 自动生成的索引存在时才重命名（避免重复运行报错）。
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_indexes "
        "           WHERE indexname = 'ix_cepci_index_series_year') "
        "AND NOT EXISTS (SELECT 1 FROM pg_indexes "
        "                 WHERE indexname = 'ix_cepci_year') "
        "THEN "
        "ALTER INDEX ix_cepci_index_series_year RENAME TO ix_cepci_year; "
        "END IF; "
        "END $$"
    )

    # G. ix_restriction_results_record_hash（p6_1_002 声明，pcs_test 漏配）
    op.create_index(
        "ix_restriction_results_record_hash",
        "restriction_results",
        ["record_hash"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """本迁移为「drift 修复」迁移，downgrade 故意 NO-OP.

    设计原因：
    - upgrade 修复 4 类 schema drift（design_stage server_default / 3 索引 /
      1 UNIQUE 约束），这些都是被现有迁移（p4_sup008 / p5_open_005 /
      p3sim_streams_sim_fields / p6_4_001 / p1_sprint3_nullable）声明但 pcs_test
      未落的元素。
    - 若本迁移 downgrade 删除这些元素，会让 round-trip 测试
      ``test_reversible_segment_roundtrip`` 在后续 p6_4_001 / p3sim 迁移的
      downgrade 中再次失败（"index does not exist"）。
    - 不删除这些元素，由其原始迁移的 downgrade 自然清理：
      * p4_sup008 / p5_open_005 DROP COLUMN design_stage（连同 DEFAULT 一起丢）
      * p3sim_streams_sim_fields DROP INDEX ix_streams_simulation_status /
        ix_streams_estimated
      * p6_4_001 DROP INDEX ix_compound_heating_values_hhv
      * p1_sprint3_nullable DROP CONSTRAINT uq_equipment_type_codes_project_type
    - 这是 drift 修复迁移的标准模式（P6-9-PICKUP-2 F2 patch commit 0c631c3 +
      P6-9-PICKUP-3 T2 8b505cb 已用相同模式）。
    """
    # NO-OP：所有 schema 元素由其原始迁移的 downgrade 清理。
    pass
