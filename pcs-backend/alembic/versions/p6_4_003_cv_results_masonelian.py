"""P6-4 cv_results 加 1 列 masonelian_model（C-24 Masonelian fl / SPEC §3.2.1.5）。

依据：

- P6-4 计划 Task 5（C-24 Masonelian fl；T5 实施）。
- V1.2 D3 裁决：仅加 1 列 nullable ``masonelian_model``；``fl`` / ``flash_steam_rate_kg_s``
  走 ``_build_output_json`` JSONB 容器（cerebrum.md Do-Not-Repeat：避免 alembic 单列
  迁移开销；JSONB 容器透传已能容纳新字段）。
- D5 三级验收：3 模型并存，``masonelian_model`` 字段标记口径。

设计要点：

- 1 列 nullable 不破坏 V1.0/V1.1 既有 cv_results 行（新字段默认 NULL；后续 CvEngine
  集成时填充）。
- 列定义严格对齐 ``app/services/cv/flashing_correction.py:_KNOWN_MASONELIAN_MODELS``
  （MASONELIAN_1973 / CHAPMAN_JANS / TONG）。
- 不下沉 fl / flash_steam_rate_kg_s（V1.2 D3 明确）。

DOWN-REVISION = ``p6_4_002_vessel_results_sizing``（T2 落地后 alembic head；
2026-09-25 由 Task 2 提交；0355d08）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_4_003_cv_results_masonelian"
down_revision = "p6_4_002_vessel_results_sizing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """cv_results 加 1 列 masonelian_model（C-24 V1.2 D3 严格 1 列）。

    1 列 nullable（不破坏 V1.0/V1.1 既有 cv_results 行）：
      - masonelian_model String(32) NULL：MASONELIAN_1973 / CHAPMAN_JANS / TONG
        （SPEC §3.2.1.5 Eq.5 模型口径；CvEngine 集成时填充）
    """
    op.add_column(
        "cv_results",
        sa.Column(
            "masonelian_model", sa.String(length=32), nullable=True,
            comment=(
                "Masonelian fl 模型口径 [SPEC §3.2.1.5]："
                "MASONELIAN_1973（默认 Eq.5）/ CHAPMAN_JANS / TONG"
            ),
        ),
    )


def downgrade() -> None:
    """cv_results 删 1 列 masonelian_model（Task 5 测试 / 回滚用）。"""
    op.drop_column("cv_results", "masonelian_model")