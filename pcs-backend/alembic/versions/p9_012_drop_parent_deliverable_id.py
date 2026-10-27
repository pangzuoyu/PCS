"""删死列 `deliverables.parent_deliverable_id`（P9B-2 · T-2 · 用户 2026-10-27 裁决）。

## 为什么现在删最便宜

- **0 行数据**（开发阶段 `deliverables` 空）⇒ 无回填、无兼容窗口；
- **0 处写入**（全仓只有 model / schema 的声明 ⇒ `grep` 只命中那两处）；
- **R-13 之后零依赖**（聚合端点不再反查变更单 —— 变更单**自己就是交付物**，
  `deliverable_type=CHANGE_NOTICE`）。

⇒ 留着它**唯一的后果是误导**：下一个读 `app/models/deliverable.py` 的人会以为
「变更单挂在父交付物上」，而事实相反。

## 为什么现在删（而不是以后）

开发阶段是删死列成本最低的时机（0 行 ⇒ 无回填、无下游通知、无兼容窗口）。

## ⚠️ `downgrade` 是**有损**的

降级只能把列**加回来**（数据回不来）⇒ 这是删列的固有代价，不在降级路径里修。

## Revision

`revision = p9_012`，`down_revision = p9_011`（当前 head）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p9_012"
down_revision = "p9_011"
branch_labels = None
depends_on = None

_TABLE = "deliverables"
_COLUMN = "parent_deliverable_id"


def upgrade() -> None:
    """删掉死列（⚠️ 不可逆：数据不保留）。"""
    # ⚠️ `op.drop_column` 的签名是 `(table_name, column_name)` —— 位置参数顺序
    #    与 `add_column` 一样，**不是** `(column_name, table_name=...)`。
    op.drop_column(_TABLE, _COLUMN)


def downgrade() -> None:
    """把列**加回来**（⚠️ **有损** —— 数据回不来）。

    原列定义：`Uuid` / nullable / FK → `deliverables.deliverable_id`。
    """
    op.add_column(
        _TABLE,
        sa.Column(_COLUMN, sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_deliverables_parent_deliverable_id_deliverables",
        _TABLE,
        _TABLE,
        [_COLUMN],
        ["deliverable_id"],
    )
