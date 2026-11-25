"""p10_007：模板的「默认单位制」+「BEDD 默认值」两列（P10-K · TODO-210 · D1/D3 裁决）。

## 为什么

2026-11-25 人裁（§7.10.6 复核后的 D1 / D3）：

- **D1** —— 模板的「默认单位制」= **默认值** ⇒ ⇒ ⇒ **用户显式选过 ⇒ ⇒ ⇒
  不覆盖** ⇒ ⇒ ⇒ 「用户动没动过」**由前端判定** ⇒ ⇒ ⇒ 前端传「单位制由谁
  决定」⇒ ⇒ ⇒ 后端**不猜**；
- **D3** —— 模板的「BEDD_JSON 默认结构」= **模板预填默认值** ⇒ ⇒ ⇒ apply
  **只填空缺** ⇒ ⇒ ⇒ 与「输入清单」**完全同款**（按 key 幂等）。

⇒ ⇒ ⇒ 这两个值**需要落到模板上** ⇒ ⇒ ⇒ ⇒ 而模板表今天**只有**
`default_config_json`（7 段的 pydantic 模型）⇒ ⇒ ⇒ **塞不进去**
⇒ ⇒ ⇒ ⇒ 多出来的键会被**静默丢弃**（= bug-2210 同款）⇒ ⇒ ⇒ ⇒
**必须各占一列**。

## 列形状

| 列 | 类型 | 可空 | 含义 |
|---|---|---|---|
| `unit_system` | `VARCHAR(2)` | ✔ | 模板的**默认**单位制（SI / US）⇒ ⇒ ⇒ NULL = 该模板**不带**默认单位制 ⇒ ⇒ ⇒ apply 时**不动**项目的单位制 |
| `bedd_defaults_json` | `JSONB` | ✔ | `{"分组.字段": 值}`（如 `{"meteorology.pressure": 101.325}`）⇒ ⇒ ⇒ apply 时**只填空缺** |

⚠️ **`unit_system` 的 CHECK 允许 NULL** ⇒ ⇒ ⇒ 「没带默认单位制」的模板
**合法** ⇒ ⇒ ⇒ 而非空值只能取 `SI` / `US`（与 `projects.unit_system`
**同一个词表** `UnitSystem`）。

⚠️ **两列都可空** ⇒ ⇒ ⇒ 存量行**不需要回填** ⇒ ⇒ ⇒ 存量模板（`p10_006`
种的那两条）**没有**默认单位制 ⇒ ⇒ ⇒ apply 时**不动**项目的单位制
⇒ ⇒ ⇒ ⇒ **行为与本迁移前完全一致**。

## Revision

`revision = p10_007`，`down_revision = p10_006`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p10_007"
down_revision = "p10_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加两列（**全可空** ⇒ ⇒ 存量行不需要回填）+ 一条 CHECK。"""
    op.add_column(
        "project_templates",
        sa.Column("unit_system", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "project_templates",
        sa.Column("bedd_defaults_json", JSONB(), nullable=True),
    )
    op.create_check_constraint(
        "ck_project_templates_unit_system",
        "project_templates",
        "unit_system IS NULL OR unit_system IN ('SI', 'US')",
    )


def downgrade() -> None:
    """反向：先删 CHECK，再删列（**顺序也要一致**）。"""
    op.drop_constraint(
        "ck_project_templates_unit_system", "project_templates", type_="check"
    )
    op.drop_column("project_templates", "bedd_defaults_json")
    op.drop_column("project_templates", "unit_system")
