"""p7_s5_001: 删除 `equipment_lib` 死表（设备库实际由 ConfigAsset CATEGORY_6 承载）.

裁决依据（2026-10-06 全量实证，详见 `docs/PCS-NOTE-equipment_lib-废弃-2026-10-06.md`）:

`equipment_lib` 表自 2026-08-31 随 v3.1 基线（`dd47298c9c38`）一次性生成后,
**从未被使用**:

| 维度 | `equipment_lib` | `ConfigAsset` + CATEGORY_6 |
|---|---|---|
| SPEC 授权 | **无** —— P2 §3.2.6 标题即「复用设备库管理（**CATEGORY_6**）」 | SPEC 定义的正式承载 |
| 实现 | 无 | P2 Sprint 1.9 `f0652ae`（2026-09-06, 248 行 + 5 测试） |
| 代码引用 | 0（仅 ORM 自指） | 4 处（service / api / tests） |
| 专属测试 | 0（`test_schema.py` 仅表名字符串） | `tests/api/v1/test_equip_lib.py` |
| 库内行数 | 0（pcs + pcs_test 均空） | 0 |

`docs/adr/0032-vessel-process-calculation.md:186-201` 曾以「本表 0 行」为由把
P5-1-3 `recommend_vessels`（按相似度推荐设备）判为 DEFERRED —— 但该核实做于
2026-09-17, 早在 P2 Sprint 1.9（2026-09-06）把沉淀接到 ConfigAsset 之后,
**前提当日即已过时**。本迁移同时解除该错误阻塞。

⚠️ 本表数据本就为 0（`select count(*) from equipment_lib` → 0, pcs 库实测
2026-10-06）, 删除无数据损失。若某环境确有数据, 请先备份再 upgrade。

Revision ID: p7_s5_001
Revises: p7_s4_002
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_001"
down_revision = "p7_s4_002"
branch_labels = None
depends_on = None

_TABLE = "equipment_lib"


def upgrade() -> None:
    """删除 equipment_lib（幂等: 表不存在时不报错）."""
    op.drop_table(_TABLE, if_exists=True)


def downgrade() -> None:
    """重建 equipment_lib（回滚兜底; 无 ORM 映射, 仅供 schema 往返）.

    字段与 `dd47298c9c38:113-128` 保持一致, 便于「降级 → 再升级」后

    字段与 `dd47298c9c38:113-128` 保持一致, 便于「降级 → 再升级」后
    schema 形态可预期。注意重建后仍无任何代码写入 —— 它是死表。
    """
    op.create_table(
        _TABLE,
        sa.Column("equip_id", sa.Uuid(), primary_key=True),
        sa.Column("type_code", sa.String(5), nullable=False),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("material", sa.String(100), nullable=True),
        sa.Column("standard_drawing_no", sa.String(100), nullable=True),
        sa.Column("process_description", sa.Text(), nullable=True),
        sa.Column("cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("cost_currency", sa.String(10), nullable=True),
        sa.Column("cost_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("equip_id", name=op.f("pk_equipment_lib")),
    )
