"""P8c：heat_results 加用户 2026-12-12 裁决要进规格书的 3 组字段.

壁温 2 列 + 管排数 1 列。

| 裁决 | 列 |
|---|---|
| 壁温进规格书 | `skin_temp_min` / `skin_temp_max`（FLOAT，°C） |
| 管排数空冷器专属 | `tube_rows`（INTEGER） |

**为什么壁温是两个列**：HTRI 的 `Skin temperature, Min/Max` 是一个标签
两个值（`39.24 | 91.03 | 39.60 | 93.42` = 空气侧/管程侧 × min/max）。
本批只取**管程侧**（换热器管壁温度），故两个列。两侧都取的话是四个列 ——
等确认规格书要哪一侧再加。

**为什么 `tube_rows` 是 INTEGER 而不是 Float**：`Tubepasses/Tuberows` 是
`2 / 4`，管排数恒为整数。存成 Float 会在报表里显示成 `4.0`。

⚠️ **这三列目前没有 HTRI 导入写入方**（`htri_parser` 只提 16 个字段）。
手工录入（`HeatCalcInput`）能填。导入的那批行会是 NULL —— 这是**已知的
诚实缺口**，不是被藏起来的缺陷：
`tests/services/report/test_heat_spec_confirmed_fields.py` 钉住这一点，
解析器补上时会被迫同步更新。

**幂等**：`ADD COLUMN IF NOT EXISTS`。**不套用 p8_001 的 drop-then-create**
—— `heat_results` 会有真实数据，drop 一次就是一次全表删除。
"""
from __future__ import annotations

from alembic import op

revision = "p8_003"
down_revision = "p8_002"
branch_labels = None
depends_on = None

_NEW_COLUMNS = (
    ("skin_temp_min", "DOUBLE PRECISION"),
    ("skin_temp_max", "DOUBLE PRECISION"),
    ("tube_rows", "INTEGER"),
)


def upgrade() -> None:
    """加三列。幂等：ADD COLUMN IF NOT EXISTS."""
    for name, sql_type in _NEW_COLUMNS:
        op.execute(f"ALTER TABLE heat_results ADD COLUMN IF NOT EXISTS {name} {sql_type}")


def downgrade() -> None:
    """删三列。幂等：DROP COLUMN IF EXISTS."""
    for name, _sql_type in reversed(_NEW_COLUMNS):
        op.execute(f"ALTER TABLE heat_results DROP COLUMN IF EXISTS {name}")
