"""p7_s5_003: 修正 2 张表的 created_by 列类型 + 1 张表的 JSON 列类型.

发现路径（2026-10-06 索引漂移核销后，`alembic check` 露出的 5 条 modify_type）:
ORM 声明的列类型与 DB 实际不一致。逐条查证后判定 **DB 侧写错了，不是 ORM 落后**。

1. `created_by` CHAR(32) → UUID（2 张表）
   - `pipe_class_import_previews` / `project_template_pipe_classes`
   - 全库 51 张表的 `created_by` 都是 `uuid`，**只有这 2 张是 `char(32)`**
   - 罪魁祸首: `p6_5_006_orm_db_drift_final_fix.py:48` 用
     `ADD COLUMN IF NOT EXISTS created_by CHAR(32)` 补列 —— 补对了名字，
     补错了类型。`TimestampMixin.created_by` 声明的是 `Mapped[uuid.UUID | None]`
   - 影响: 该列写入 UUID 时 PG 会 `uuid::text` 得 36 字符 > 32 报
     "value too long for type character(32)"。目前未爆发，因为两表皆 0 行
     且业务代码走 `actor_id` 而非 `created_by`（见
     `pipe_class_import_service.py:129`）

2. `override_json` / `snapshot_json` JSON → JSONB（`project_pipe_classes`）
   - 全库 156 个 JSON 列是 `jsonb`，只有 9 个是 `json`，这 2 个在少数派里
   - ORM 本就声明 JSONB；PG 的 `json` 不可建 GIN 索引且解析更慢

⚠️ 三张表实测均 0 行，类型转换零数据风险。若某环境有数据，
`char(32)::uuid` 会在非 UUID 文本上抛错，请先核对。

Revision ID: p7_s5_003
Revises: p7_s5_002
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_003"
down_revision = "p7_s5_002"
branch_labels = None
depends_on = None

# created_by 误建成 char(32) 的两张表（p6_5_006 补列时写错类型）
_CHAR32_TABLES = (
    "pipe_class_import_previews",
    "project_template_pipe_classes",
)
# 少数派 json 列（应随全库 156 列的 jsonb 规范）
_JSON_COLUMNS = ("override_json", "snapshot_json")
_JSON_TABLE = "project_pipe_classes"


def upgrade() -> None:
    """char(32) → uuid；json → jsonb."""
    for table in _CHAR32_TABLES:
        op.alter_column(
            table,
            "created_by",
            type_=sa.Uuid(),
            existing_type=sa.String(32),
            existing_nullable=True,
            postgresql_using="created_by::uuid",
        )
    for column in _JSON_COLUMNS:
        op.alter_column(
            _JSON_TABLE,
            column,
            type_=postgresql.JSONB(),
            existing_type=sa.JSON(),
            postgresql_using=f"{column}::jsonb",
        )


def downgrade() -> None:
    """回退: uuid → char(32)；jsonb → json."""
    for column in reversed(_JSON_COLUMNS):
        op.alter_column(
            _JSON_TABLE,
            column,
            type_=sa.JSON(),
            existing_type=postgresql.JSONB(),
            postgresql_using=f"{column}::json",
        )
    for table in reversed(_CHAR32_TABLES):
        op.alter_column(
            table,
            "created_by",
            type_=sa.String(32),
            existing_type=sa.Uuid(),
            existing_nullable=True,
            postgresql_using="created_by::text",
        )
