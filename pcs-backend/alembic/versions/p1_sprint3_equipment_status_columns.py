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
    """equipment_list 补 3 个状态列（P1 Sprint3 DICT-002 设备字典）。

    步骤（A → E 共 5 段）：
    - A. 创建 3 个 PG native enum：equipmentstatus（N/E/D/M/F 单字母）/
      calcstatus（NOT_CALCULATED/CALCULATING/COMPLETED/NEED_RECALC）/
      actualdatastatus（NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC）
    - B. equipment_status varchar(1) NOT NULL default 'N'（生命周期分类）
    - C. calc_status native enum NOT NULL default 'NOT_CALCULATED'
    - D. actual_data_status native enum NOT NULL default 'NOT_ENTERED'
    - E. 索引：calc_status + actual_data_status（CIA 扫描加速）

    业务：DICT-ALL-003 V3.3 §2.4 ADR-0025 三状态机落地，equipment_list
    接入 CIA 计算编排与设备联动关闭流程。
    """
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
