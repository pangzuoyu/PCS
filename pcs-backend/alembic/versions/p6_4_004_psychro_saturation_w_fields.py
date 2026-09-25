"""P6-4 psychro_results 加 4 列 saturation W（C-17 显式水含量 / SPEC §3.2.5 P6-PSY-001）。

依据：

- P6-4 计划 Task 4（C-17 显式水含量；T4 实施）。
- V1.2 D3 严格 4 列 nullable：仅追加，不破坏 V1.0/V1.1 既有 psychro_results 行。
- D14 lru_cache 性能优化（service 层）+ D5 三级验收（ASHRAE Fundamentals 2021
  黄金标准）— DB 层只负责落库，ASHRAE 对账走 service 单元测试。

设计要点：

- 4 列 nullable（不破坏 V1.0 既有 psychro_results 行）：
  - saturation_w_kg_kg Float NULL：饱和 W（kg 水 / kg 干空气）— 摩尔比
  - saturation_w_mg_sm3 Float NULL：饱和 W（mg 水 / Sm³ 干空气）— 西欧常用
  - saturation_w_lb_per_mmscf Float NULL：饱和 W（lb 水 / MMscf 干空气）— 北美常用
  - saturation_T_c Float NULL：饱和温度 °C（service 入参温度回显）
- 列定义严格对齐 ``app/services/psychro/saturation_water_content_service.py``
  ``SaturationWaterContentResult`` 字段。
- calc_type 字符串新增 ``SATURATION_W_CALC`` 字面（与 6 既有 calc_type 并列；
  psychro_results.calc_type 列定义已兼容 String(32)，无需 schema 变更）。

DOWN-REVISION = ``p6_4_003_cv_results_masonelian``（T5 落地后 alembic head；
2026-09-25 由 Task 5 提交；134e26b）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_4_004_psychro_saturation_w_fields"
down_revision = "p6_4_003_cv_results_masonelian"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """psychro_results 加 4 列 saturation W（C-17 V1.2 严格 4 列）。

    4 列 nullable（不破坏 V1.0/V1.1 既有 psychro_results 行）：
      - saturation_w_kg_kg Float NULL：饱和 W kg 水 / kg 干空气（SPEC §3.2.5）
      - saturation_w_mg_sm3 Float NULL：饱和 W mg 水 / Sm³ 干空气（西欧）
      - saturation_w_lb_per_mmscf Float NULL：饱和 W lb 水 / MMscf 干空气（北美）
      - saturation_T_c Float NULL：饱和温度 °C（service 入参回显）
    """
    op.add_column(
        "psychro_results",
        sa.Column(
            "saturation_w_kg_kg", sa.Float(), nullable=True,
            comment=(
                "饱和水含量 kg 水/kg 干空气"
                "[SATURATION_W_CALC 专用；SPEC §3.2.5 P6-PSY-001 §3.9.2]"
            ),
        ),
    )
    op.add_column(
        "psychro_results",
        sa.Column(
            "saturation_w_mg_sm3", sa.Float(), nullable=True,
            comment=(
                "饱和水含量 mg 水/Sm³ 干空气"
                "[SATURATION_W_CALC；西欧常用单位]"
            ),
        ),
    )
    op.add_column(
        "psychro_results",
        sa.Column(
            "saturation_w_lb_per_mmscf", sa.Float(), nullable=True,
            comment=(
                "饱和水含量 lb 水/MMscf 干空气"
                "[SATURATION_W_CALC；北美常用单位]"
            ),
        ),
    )
    op.add_column(
        "psychro_results",
        sa.Column(
            "saturation_T_c", sa.Float(), nullable=True,
            comment=(
                "饱和温度 °C [SATURATION_W_CALC；service 入参温度回显]"
            ),
        ),
    )


def downgrade() -> None:
    """psychro_results 删 4 列 saturation W（Task 4 测试 / 回滚用）。"""
    op.drop_column("psychro_results", "saturation_T_c")
    op.drop_column("psychro_results", "saturation_w_lb_per_mmscf")
    op.drop_column("psychro_results", "saturation_w_mg_sm3")
    op.drop_column("psychro_results", "saturation_w_kg_kg")