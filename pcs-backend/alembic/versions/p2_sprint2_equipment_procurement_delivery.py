"""P2 Sprint 2：equipment_list 扩容（采购 10 + 图纸 3 + 交付 5 + 安装 5 + 重量 3 = 26 项）。

跳过：
- vendor（item 15）：Task 3.1 已新增
- installation_location（item 39）：Task 3.1 已由 install_location 重命名
- net_weight（item 43）：Task 3.1 已由 weight_kg 重命名
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sprint2_equipment_procurement_delivery"
down_revision: str | None = "p2_sprint2_equipment_naming_fix"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # §四 采购（items 16-25，跳过 15 vendor）
    op.add_column(
        "equipment_list", sa.Column("alternate_vendor", sa.String(200), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("order_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "equipment_list",
        sa.Column("purchase_order_number", sa.String(100), nullable=True),
    )
    op.add_column(
        "equipment_list", sa.Column("cost", sa.Numeric(18, 2), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("cost_currency", sa.String(10), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("cost_source", sa.String(200), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("cost_year", sa.Integer(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("gpe_spec_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("gpe_spec_status", sa.String(20), nullable=True)
    )
    op.add_column(
        "equipment_list",
        sa.Column("specification_priority", sa.String(100), nullable=True),
    )

    # §五 图纸（items 26-28）
    op.add_column(
        "equipment_list",
        sa.Column("approval_drawing_received_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "equipment_list",
        sa.Column("approval_drawing_return_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "equipment_list",
        sa.Column("certified_drawing_received_date", sa.Date(), nullable=True),
    )

    # §六 交付（items 29-33）
    op.add_column(
        "equipment_list", sa.Column("delivery_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("actual_received_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("forecast_on_site", sa.Date(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("actual_on_site", sa.Date(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("storage_location", sa.String(200), nullable=True)
    )

    # §七 安装（items 34-38，跳过 39 installation_location：3.1 已重命名）
    op.add_column(
        "equipment_list",
        sa.Column("installation_contract_number", sa.String(100), nullable=True),
    )
    op.add_column(
        "equipment_list",
        sa.Column("installation_notes", sa.String(500), nullable=True),
    )
    op.add_column(
        "equipment_list",
        sa.Column(
            "installation",
            sa.String(50),
            nullable=True,
            comment="安装方式（MEI/吊装/现场组装）",
        ),
    )
    op.add_column(
        "equipment_list", sa.Column("unloading", sa.String(200), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("loading_by", sa.String(100), nullable=True)
    )

    # §八 重量（items 40-42，跳过 43 net_weight：3.1 已重命名）
    op.add_column(
        "equipment_list", sa.Column("empty_weight", sa.Float(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("full_weight", sa.Float(), nullable=True)
    )
    op.add_column(
        "equipment_list", sa.Column("weigh_cells", sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    # §八 重量（逆向）
    op.drop_column("equipment_list", "weigh_cells")
    op.drop_column("equipment_list", "full_weight")
    op.drop_column("equipment_list", "empty_weight")

    # §七 安装（逆向）
    op.drop_column("equipment_list", "loading_by")
    op.drop_column("equipment_list", "unloading")
    op.drop_column("equipment_list", "installation")
    op.drop_column("equipment_list", "installation_notes")
    op.drop_column("equipment_list", "installation_contract_number")

    # §六 交付（逆向）
    op.drop_column("equipment_list", "storage_location")
    op.drop_column("equipment_list", "actual_on_site")
    op.drop_column("equipment_list", "forecast_on_site")
    op.drop_column("equipment_list", "actual_received_date")
    op.drop_column("equipment_list", "delivery_date")

    # §五 图纸（逆向）
    op.drop_column("equipment_list", "certified_drawing_received_date")
    op.drop_column("equipment_list", "approval_drawing_return_date")
    op.drop_column("equipment_list", "approval_drawing_received_date")

    # §四 采购（逆向）
    op.drop_column("equipment_list", "specification_priority")
    op.drop_column("equipment_list", "gpe_spec_status")
    op.drop_column("equipment_list", "gpe_spec_number")
    op.drop_column("equipment_list", "cost_year")
    op.drop_column("equipment_list", "cost_source")
    op.drop_column("equipment_list", "cost_currency")
    op.drop_column("equipment_list", "cost")
    op.drop_column("equipment_list", "purchase_order_number")
    op.drop_column("equipment_list", "order_date")
    op.drop_column("equipment_list", "alternate_vendor")