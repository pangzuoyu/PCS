"""P6-4 vessel_results 加 6 列 sizing（C-08 两相分离器尺寸 / SPEC §3.4.2 V1.2).

依据：

- P6-4 计划 Task 2（C-08 sizing；T2 实施）。
- WS-CA-PR-010 Rev A 5 段计算输出（vmax / csa_min / csa_actual /
  nozzle_min_id / control_height / residence_time）。
- V1.2 完全重写（**不是** V1.0/V1.1 weight_kg/weight_method）：
  - vmax_m_s: Souders-Brown 最大允许气速
  - csa_min_m2: 最小所需气相 CSA（85% 利用率）
  - csa_actual_m2: 实际气相 CSA = π·D²/4
  - nozzle_min_id_m: 入口喷嘴最小内径（动量校核）
  - control_height_m: 仪表控制高度 = t_c × Q_total / (3600 × CSA)
  - residence_time_s: 实际停留时间

设计要点：

- 6 列 nullable（不破坏 V1.0 现有 sizing 行；新 sizing 路径填充）。
- 列定义严格对齐 ``app/services/vessel/two_phase_separator_sizing_service.py``
  TwoPhaseSeparatorSizingResult 字段。
- 不下沉 weight_kg / weight_method（V1.0 重量估算路径已废弃）。
- 不抽 WeightSegment 到 vessel/_shared_segments.py（V1.0 污染禁止）。

DOWN-REVISION = ``p6_4_001_compound_heating_values``（T1 落地后 alembic head；
2026-09-25 由 Task 1 提交）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p6_4_002_vessel_results_sizing"
down_revision = "p6_4_001_compound_heating_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """vessel_results 加 6 列 sizing（C-08 V1.2 重写).

    6 列 nullable（不破坏 V1.0 现有 sizing 行）：
      - vmax_m_s Float NULL：Souders-Brown Vmax
      - csa_min_m2 Float NULL：最小气相 CSA（85% 利用率）
      - csa_actual_m2 Float NULL：实际气相 CSA = π·D²/4
      - nozzle_min_id_m Float NULL：入口喷嘴最小内径
      - control_height_m Float NULL：仪表控制高度
      - residence_time_s Float NULL：实际停留时间
    """
    op.add_column(
        "vessel_results",
        sa.Column(
            "vmax_m_s", sa.Float(), nullable=True,
            comment="Souders-Brown Vmax = K × √((ρL − ρV) / ρV) [WS-CA-PR-010 §4.2]",
        ),
    )
    op.add_column(
        "vessel_results",
        sa.Column(
            "csa_min_m2", sa.Float(), nullable=True,
            comment="最小所需气相 CSA = Q_gas / (Vmax × 0.85) [WS-CA-PR-010 §4.3]",
        ),
    )
    op.add_column(
        "vessel_results",
        sa.Column(
            "csa_actual_m2", sa.Float(), nullable=True,
            comment="实际气相 CSA = π·D²/4 [WS-CA-PR-010 §4.3]",
        ),
    )
    op.add_column(
        "vessel_results",
        sa.Column(
            "nozzle_min_id_m", sa.Float(), nullable=True,
            comment="入口喷嘴最小内径 = √(4m²/(π·N·ρ_mix)) [WS-CA-PR-010 §5.1]",
        ),
    )
    op.add_column(
        "vessel_results",
        sa.Column(
            "control_height_m", sa.Float(), nullable=True,
            comment="仪表控制高度 H_c = t_c × Q / (3600·CSA) [WS-CA-PR-010 §5.3]",
        ),
    )
    op.add_column(
        "vessel_results",
        sa.Column(
            "residence_time_s", sa.Float(), nullable=True,
            comment="实际停留时间 V_total / Q_per_vessel_m3_s [WS-CA-PR-010 §5]",
        ),
    )


def downgrade() -> None:
    """vessel_results 删 6 列 sizing（Task 2 测试 / 回滚用）."""
    op.drop_column("vessel_results", "residence_time_s")
    op.drop_column("vessel_results", "control_height_m")
    op.drop_column("vessel_results", "nozzle_min_id_m")
    op.drop_column("vessel_results", "csa_actual_m2")
    op.drop_column("vessel_results", "csa_min_m2")
    op.drop_column("vessel_results", "vmax_m_s")