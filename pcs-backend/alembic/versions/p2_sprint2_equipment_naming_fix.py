"""P2 Sprint 2：equipment_list 命名修正（7 项）。"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sprint2_equipment_naming_fix"
down_revision: str | None = "p2_sprint1_config_layer_fix"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 6 个简单重命名
    op.alter_column(
        "equipment_list", "description", new_column_name="equipment_description"
    )
    op.alter_column(
        "equipment_list", "install_location", new_column_name="installation_location"
    )
    op.alter_column("equipment_list", "weight_kg", new_column_name="net_weight")
    op.alter_column("equipment_list", "paint_spec", new_column_name="paint")
    op.alter_column(
        "equipment_list", "drawing_no", new_column_name="flowsheet_drawing_number"
    )
    op.alter_column(
        "equipment_list",
        "engineering_notes",
        new_column_name="process_engineering_remarks",
    )

    # vendor_id (FK→suppliers) → vendor (string 200) 三步走
    # Step 1: 新增 vendor 字符串列（nullable）
    op.add_column(
        "equipment_list", sa.Column("vendor", sa.String(200), nullable=True)
    )
    # Step 2: 数据回填（仅当 suppliers 表存在时执行）
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppliers" in inspector.get_table_names():
        op.execute(
            "UPDATE equipment_list SET vendor = "
            "(SELECT supplier_name FROM suppliers "
            "WHERE supplier_id = equipment_list.vendor_id) "
            "WHERE vendor_id IS NOT NULL AND vendor IS NULL"
        )
    # Step 3: 删除 vendor_id FK + 列
    # ORM 中 vendor_id 是裸 UUID 列（无 FK 声明）；DB 中可能存在也可能不存在 FK
    fk_names = [
        fk["name"]
        for fk in inspector.get_foreign_keys("equipment_list")
        if "vendor" in (fk.get("constrained_columns") or [])
    ]
    for fk_name in fk_names:
        op.drop_constraint(fk_name, "equipment_list", type_="foreignkey")
    if not fk_names:
        print("no vendor FK constraint found, skipping drop_constraint")
    op.drop_column("equipment_list", "vendor_id")


def downgrade() -> None:
    # 恢复 vendor_id 列
    op.add_column(
        "equipment_list",
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
    )
    # 尝试恢复 FK（若 suppliers 存在）
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "suppliers" in inspector.get_table_names():
        existing_fks = [
            fk["name"]
            for fk in inspector.get_foreign_keys("equipment_list")
            if "vendor_id" in (fk.get("constrained_columns") or [])
        ]
        if not existing_fks:
            op.create_foreign_key(
                "equipment_list_vendor_id_fkey",
                "equipment_list",
                "suppliers",
                ["vendor_id"],
                ["supplier_id"],
            )
    op.drop_column("equipment_list", "vendor")

    # 反向重命名
    op.alter_column(
        "equipment_list",
        "process_engineering_remarks",
        new_column_name="engineering_notes",
    )
    op.alter_column(
        "equipment_list",
        "flowsheet_drawing_number",
        new_column_name="drawing_no",
    )
    op.alter_column("equipment_list", "paint", new_column_name="paint_spec")
    op.alter_column("equipment_list", "net_weight", new_column_name="weight_kg")
    op.alter_column(
        "equipment_list", "installation_location", new_column_name="install_location"
    )
    op.alter_column(
        "equipment_list", "equipment_description", new_column_name="description"
    )