"""P4-4 sim_imports.preview_towers_json 列扩展（P4 #4 parser 入库链路）。

按 P4 首批 #4 修复 parser → DB 链路：

1. **sim_imports 加 preview_towers_json JSONB 列**（default `[]`）：
   - preview 阶段 PRO/II parser 解析的 COLUMN SUMMARY 段落库
   - commit 阶段读 → 写 sim_tower_results 行（SIM-16 表）

2. **不动 sim_tower_results 表结构**（已有 import_id FK）

3. **存量回填**：`[]`（历史 preview 行无 tower 信息）

**DOWN-REVISION** = p5_open_010_psv_valve_selection（P5-OPEN-10 末态 alembic head）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p4_4_sim_import_preview_towers"
down_revision = "p5_open_010_psv_valve_selection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加 preview_towers_json 列（默认 `[]`，兼容老 preview 行）。"""
    op.add_column(
        "sim_imports",
        sa.Column(
            "preview_towers_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    """DROP preview_towers_json 列。"""
    op.drop_column("sim_imports", "preview_towers_json")


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]
