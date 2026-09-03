"""Sprint 3：equipment_list 补 actual_data_status / calc_status / equipment_status 列。

DICT-ALL-003 V3.3 §2.4（ADR-0025）+ DICT-002 设备表字典：
- equipment_status：N=New/E=Existing/D=Delete/M=Modified/F=Future（DICT-002 单字母）
- calc_status：NOT_CALCULATED/CALCULATING/COMPLETED/NEED_RECALC
- actual_data_status：NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC

P1-MVP 关闭后由烧烤 session D3.3 裁决。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p1_sprint3_equipment_status_columns"
down_revision: str | None = "p1_sprint3_nullable_equipment_type_codes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. 创建 3 个 PG enum 类型
    equipment_status = sa.Enum("N", "E", "D", "M", "F", name="equipmentstatus")
    equipment_status.create(op.get_bind(), checkfirst=True)

    calc_status = sa.Enum(
        "NOT_CALCULATED",
        "CALCULATING",
        "COMPLETED",
        "NEED_RECALC",
        name="calcstatus",
    )
    calc_status.create(op.get_bind(), checkfirst=True)

    actual_data_status = sa.Enum(
        "NOT_ENTERED",
        "PENDING_CONFIRM",
        "CONFIRMED",
        "NEED_RECALC",
        name="actualdatastatus",
    )
    actual_data_status.create(op.get_bind(), checkfirst=True)

    # 2. equipment_status：String(1)，已有行默认 'N'
    op.add_column(
        "equipment_list",
        sa.Column(
            "equipment_status",
            sa.String(length=1),
            nullable=False,
            server_default="N",
            comment="设备生命周期分类：N=New新建/E=Existing已有/D=Delete删除/M=Modified修改/F=Future预留",
        ),
    )

    # 3. calc_status：native enum
    op.add_column(
        "equipment_list",
        sa.Column(
            "calc_status",
            calc_status,
            nullable=False,
            server_default="NOT_CALCULATED",
            comment="设备计算状态：NOT_CALCULATED/CALCULATING/COMPLETED/NEED_RECALC",
        ),
    )

    # 4. actual_data_status：native enum（ADR-0025 设备联动）
    op.add_column(
        "equipment_list",
        sa.Column(
            "actual_data_status",
            actual_data_status,
            nullable=False,
            server_default="NOT_ENTERED",
            comment="供应商实际数据录入：NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC",
        ),
    )

    # 5. 索引（CIA 扫描 + 状态查询）
    op.create_index(
        "ix_equipment_list_calc_status",
        "equipment_list",
        ["calc_status"],
    )
    op.create_index(
        "ix_equipment_list_actual_data_status",
        "equipment_list",
        ["actual_data_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_equipment_list_actual_data_status", table_name="equipment_list")
    op.drop_index("ix_equipment_list_calc_status", table_name="equipment_list")
    op.drop_column("equipment_list", "actual_data_status")
    op.drop_column("equipment_list", "calc_status")
    op.drop_column("equipment_list", "equipment_status")

    sa.Enum(name="actualdatastatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="calcstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="equipmentstatus").drop(op.get_bind(), checkfirst=True)
