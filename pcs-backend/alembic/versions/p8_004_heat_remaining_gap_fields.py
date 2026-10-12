"""P8c：heat_results 补齐主表剩余 4 条缺口.

用户 2026-12-12 裁决「剩余 5 条缺口补齐」（`tube_rows` 已在 p8_003）。

| HTRI 标签 | 列 | 类别 |
|---|---|---|
| `Area ratio (fin/bare)` / `Area ratio(out/in)` | `extended_area_m2` / `bare_area_m2` | 空冷器 |
| `Ratio, Fan/bundle face area` | `fan_face_area_ratio` | 空冷器 |
| `Heat transfer safety factor` | `heat_transfer_safety_factor` | 通用 |

**为什么存面积比而不是自己算**：这两个比值的**来源是 HTRI**。
自己用「扩展面积 / 裸面积」重算，公式与 HTRI 有细微差异时，规格书上的
数字会与设计软件对不上 —— 而交付物的数字必须与设计软件一致。
导入保真优先于「少存一个派生列」。

**幂等**：`ADD COLUMN IF NOT EXISTS`。**不套用 p8_001 的 drop-then-create**
—— `heat_results` 有真实数据。
"""
from __future__ import annotations

from alembic import op

revision = "p8_004"
down_revision = "p8_003"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("extended_area_m2", "DOUBLE PRECISION"),
    ("bare_area_m2", "DOUBLE PRECISION"),
    ("fan_face_area_ratio", "DOUBLE PRECISION"),
    ("heat_transfer_safety_factor", "DOUBLE PRECISION"),
)


def upgrade() -> None:
    """加四列. 幂等: ADD COLUMN IF NOT EXISTS."""
    for name, sql_type in _NEW_COLUMNS:
        op.execute(f"ALTER TABLE heat_results ADD COLUMN IF NOT EXISTS {name} {sql_type}")


def downgrade() -> None:
    """删四列. 幂等: DROP COLUMN IF EXISTS."""
    for name, _sql_type in reversed(_NEW_COLUMNS):
        op.execute(f"ALTER TABLE heat_results DROP COLUMN IF EXISTS {name}")
