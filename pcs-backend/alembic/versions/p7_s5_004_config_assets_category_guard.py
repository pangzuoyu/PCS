"""p7_s5_004: config_assets 加 category CHECK 约束 + (category,status) 复合索引.

设备库（CATEGORY_6）地基的约束与索引部分。检索的固定过滤就是
`(category='CATEGORY_6' AND status='PUBLISHED')`，此前两列都无索引 ——
该表已有 600+ 行 CATEGORY_1，每次设备库检索都是全表扫。

`category` 取值域依 `spec/工艺专用综合计算软件——合并数据字典.md:191`
（CATEGORY_1~6）。此前无 DB 约束，拼错成 `"CATEGORY_06"` / `"EQUIP_LIB"`
会静默写出一条永远检索不到的孤儿记录 —— 恰恰发生在最需要被发现的
设备库上。

⚠️ 存量数据核查：pcs 库 config_assets 现存 644 行全部是 CATEGORY_1，
落在取值域内，加约束无失败风险。若某环境已有域外数据，ADD CONSTRAINT
会报错并回滚（PG 事务性 DDL），届时需先清理孤儿行。

Revision ID: p7_s5_004
Revises: p7_s5_003
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_004"
down_revision = "p7_s5_003"
branch_labels = None
depends_on = None

_TABLE = "config_assets"
_CONSTRAINT = "config_assets_category_chk"
_CATEGORIES = (
    "CATEGORY_1", "CATEGORY_2", "CATEGORY_3",
    "CATEGORY_4", "CATEGORY_5", "CATEGORY_6",
)
_SQL = "category IN ({})".format(", ".join(f"'{c}'" for c in _CATEGORIES))


def upgrade() -> None:
    """加 category 取值域约束 + (category, status) 复合索引."""
    op.create_index(
        "ix_config_assets_category_status",
        _TABLE,
        ["category", "status"],
        if_not_exists=True,
    )
    op.create_check_constraint(_CONSTRAINT, _TABLE, _SQL)


def downgrade() -> None:
    """移除约束与索引."""
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="check")
    op.drop_index(
        "ix_config_assets_category_status", table_name=_TABLE, if_exists=True
    )
