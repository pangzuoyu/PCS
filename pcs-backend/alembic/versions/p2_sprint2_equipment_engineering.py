"""P2 Sprint 2：equipment_list 扩容（来源 4 + 标识 5 + 类型 4 + 工程 8 = 21 项）。

跳过：
- equipment_description（§二 item 10）：Task 3.1 已由 description 重命名
- flowsheet_drawing_number（§九 item 46）：Task 3.1 已由 drawing_no 重命名
- process_engineering_remarks（§九 item 53）：Task 3.1 已由 engineering_notes 重命名
- paint（§十 item 54）：Task 3.1 已由 paint_spec 重命名

类型分组说明（与 brief 计数差异）：
- brief 标注"类型 5"，实为 4：spec §三仅含 items 11-14（4 项），brief 计数存在 +1 off-by-one。
- 实际新增 4 + 5 + 4 + 8 = 21。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sprint2_equipment_engineering"
down_revision: str | None = "p2_sprint2_equipment_procurement_delivery"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """equipment_list 工程字段扩展（P2 sprint2 equipment §一来源）。

    步骤：
    - in_package (Boolean)：是否纳入 3D/ESR/P&ID 设计包
    - data_sources (varchar 200)：数据来源说明（如"工艺询价+厂家资料+历史项目"）
    - tag_in_3d (Boolean)：3D 模型中已 tag
    - tag_in_esr (Boolean)：ESR（设备规格表）中已 tag
    - tag_in_pid (Boolean)：P&ID 中已 tag
    - engineering_lead_id (UUID FK→users)：设计负责人
    - design_review_date (Date)：设计评审日期
    - 设计数据来源 7 字段（§一）

    业务：equipment_list 扩展工程设计阶段字段，与 §二选型 + §三校核 + §四采购
    + §五到货 共 5 段累计完成全生命周期追踪。
    """
    # §一 来源（items 1-4）
    op.add_column(
        "equipment_list", sa.Column("in_package", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("data_sources", sa.String(200), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("tag_in_3d", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("tag_in_esr", sa.Boolean(), nullable=True)
    )

    # §二 标识（items 5-9；跳过 10 equipment_description：3.1 已重命名）
    op.add_column(
        "equipment_list", sa.Column("equipment_name_cn", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("package_no", sa.String(50), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("sub_project", sa.String(20), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("unit_no", sa.String(20), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("unit_name", sa.String(100), nullable=True)
    )

    # §三 类型（items 11-14）
    op.add_column(
        "equipment_list", sa.Column("equipment_sub_type", sa.String(50), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("equipment_category", sa.String(30), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("is_pressure_vessel", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "equipment_list",
        sa.Column("pressure_vessel_category", sa.String(10), nullable=True),
    )

    # §九 工程（items 44-45, 47-52；跳过 46/53：3.1 已重命名）
    op.add_column(
        "equipment_list", sa.Column("process_engineer", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("detail_engineer", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("pid_drawing_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("pid_status", sa.String(10), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("dimensions", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("registration_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("emts_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("mst_number", sa.String(100), nullable=True)
    )


def downgrade() -> None:
    # §九 工程（逆向）
    op.drop_column("equipment_list", "mst_number")
    op.drop_column("equipment_list", "emts_number")
    op.drop_column("equipment_list", "registration_number")
    op.drop_column("equipment_list", "dimensions")
    op.drop_column("equipment_list", "pid_status")
    op.drop_column("equipment_list", "pid_drawing_number")
    op.drop_column("equipment_list", "detail_engineer")
    op.drop_column("equipment_list", "process_engineer")

    # §三 类型（逆向）
    op.drop_column("equipment_list", "pressure_vessel_category")
    op.drop_column("equipment_list", "is_pressure_vessel")
    op.drop_column("equipment_list", "equipment_category")
    op.drop_column("equipment_list", "equipment_sub_type")

    # §二 标识（逆向）
    op.drop_column("equipment_list", "unit_name")
    op.drop_column("equipment_list", "unit_no")
    op.drop_column("equipment_list", "sub_project")
    op.drop_column("equipment_list", "package_no")
    op.drop_column("equipment_list", "equipment_name_cn")

    # §一 来源（逆向）
    op.drop_column("equipment_list", "tag_in_esr")
    op.drop_column("equipment_list", "tag_in_3d")
    op.drop_column("equipment_list", "data_sources")
    op.drop_column("equipment_list", "in_package")
