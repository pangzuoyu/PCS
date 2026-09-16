"""P5-0-4a Task 4a: PK rename + tag_number 统一（DICT V3.3 字典约定对齐）。

P5-0-4 拆分 4a/4b（2026-09-16 用户裁决）：
- **4a（本迁移）**：PK rename 10 表 + column_sizing.tag_number 统一
- 4b：字段平铺（SUP-001~014），延后 sprint，按 P5-1~P5-4 实际字段需求反推

**DICT V3.3 字典约定**：15 张 TaggedRecordMixin 表（除 piping）+ equipment_list
PK 命名 = `*_id`（不带 `_calc` 后缀）
（schema_compact_dict.md L387 vessel_results / L407 sep_equip / L417 heat_results /
 L438 cv_results / L451 restriction / L463 cooling_tower / L474 psychro /
 L482 open_channel / L493 filtration 等全部为 `*_id`）。

**当前 ORM 历史**：10 张表沿用 P4-0-1 v3_1_full_schema 引入的 `*_calc_id` 命名
（heat_calc_id / vessel_calc_id 等），与 DICT V3.3 不一致。

**PK rename 10 表**（移除 `_calc` 后缀，与 DICT V3.3 对齐）：
1. vessel_results: vessel_calc_id → vessel_id
2. two_phase_results: two_phase_calc_id → two_phase_id
3. sep_equip_results: sep_calc_id → sep_equip_id
4. heat_results: heat_calc_id → heat_exchanger_id
5. cv_results: cv_calc_id → cv_id
6. restriction_results: orifice_calc_id → orifice_id
7. cooling_tower_results: ct_calc_id → cooling_tower_id
8. psychro_results: psychro_calc_id → psychro_id
9. open_channel_results: channel_calc_id → open_channel_id
10. filtration_results: filter_calc_id → filter_id

**column_sizing.tag_number 统一**（P5-0 批约束 1，2026-09-16 用户裁决 Q2 路径 A）：
P5-0-1a 落地时 column_sizing 表同时存在两个位号列：
- `column_tag` str50 NOT NULL + UNIQUE(project_id, column_tag) — 业务位号字段
- `tag_number` str50 NULL — RecordMixin 通用列（来自 `_RECORD_MIXIN_COLUMNS`）

本迁移将 column_sizing 改造为「位号统一走 RecordMixin.tag_number」：
1. 删除 UNIQUE 约束 uq_column_sizing_tag
2. 删除 column_tag 列
3. tag_number 提升为 NOT NULL（覆盖 RecordMixin 默认 nullable=True）
4. 重建 UNIQUE(project_id, tag_number) 约束（沿用同名 uq_column_sizing_tag）

注意：本迁移**不做 RENAME COLUMN**，因为 tag_number 已存在（P5-0-1a 创建）；
改用「drop constraint + drop column + alter nullable + add constraint」三步走。

**DOWN-REVISION** = p5_open_005_model_extension（P5-0-1a 末态）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p5_0_4a_pk_rename_and_tag_number"
down_revision = "p5_open_005_model_extension"
branch_labels = None
depends_on = None


# 10 表 PK rename（DICT V3.3 §4.1 字典约定）
_PK_RENAMES: list[tuple[str, str, str]] = [
    # (table, old_col, new_col)
    ("vessel_results", "vessel_calc_id", "vessel_id"),
    ("two_phase_results", "two_phase_calc_id", "two_phase_id"),
    ("sep_equip_results", "sep_calc_id", "sep_equip_id"),
    ("heat_results", "heat_calc_id", "heat_exchanger_id"),
    ("cv_results", "cv_calc_id", "cv_id"),
    ("restriction_results", "orifice_calc_id", "orifice_id"),
    ("cooling_tower_results", "ct_calc_id", "cooling_tower_id"),
    ("psychro_results", "psychro_calc_id", "psychro_id"),
    ("open_channel_results", "channel_calc_id", "open_channel_id"),
    ("filtration_results", "filter_calc_id", "filter_id"),
]


def upgrade() -> None:
    # 1. PK rename 10 表（DICT V3.3 字典约定：移除 _calc 后缀）
    for table, old_col, new_col in _PK_RENAMES:
        op.alter_column(table, old_col, new_column_name=new_col)

    # 2. column_sizing.tag_number 统一（Q2 路径 A：业务位号 column_tag → 删 + tag_number NOT NULL）
    # 2a. 删除 UNIQUE(project_id, column_tag) 约束（drop column 之前必须先 drop 约束）
    op.drop_constraint("uq_column_sizing_tag", "column_sizing", type_="unique")
    # 2b. 删除业务位号字段 column_tag
    op.drop_column("column_sizing", "column_tag")
    # 2c. tag_number 提升为 NOT NULL（覆盖 RecordMixin 默认 nullable=True）
    op.alter_column(
        "column_sizing",
        "tag_number",
        existing_type=sa.String(length=50),
        nullable=False,
    )
    # 2d. 重建 UNIQUE(project_id, tag_number) 约束（沿用原约束名 uq_column_sizing_tag）
    op.create_unique_constraint(
        "uq_column_sizing_tag", "column_sizing", ["project_id", "tag_number"]
    )


def downgrade() -> None:
    # 1. column_sizing 回退：反向操作
    # 1a. 删除 UNIQUE(project_id, tag_number)
    op.drop_constraint("uq_column_sizing_tag", "column_sizing", type_="unique")
    # 1b. tag_number 回退为 NULLABLE
    op.alter_column(
        "column_sizing", "tag_number", existing_type=sa.String(length=50), nullable=True
    )
    # 1c. 恢复 column_tag 业务字段 NOT NULL
    op.add_column(
        "column_sizing",
        sa.Column("column_tag", sa.String(length=50), nullable=False),
    )
    # 1d. 恢复 UNIQUE(project_id, column_tag)
    op.create_unique_constraint(
        "uq_column_sizing_tag", "column_sizing", ["project_id", "column_tag"]
    )

    # 2. PK rename 回退（顺序与 upgrade 相反——实际无依赖，但保持对称）
    for table, old_col, new_col in reversed(_PK_RENAMES):
        op.alter_column(table, new_col, new_column_name=old_col)
