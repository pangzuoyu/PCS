"""P3.x SIM-34: 炼油专用 5 字段 + 蒸馏曲线 8 种 schema。

spec ADD-001 §3.8 + §3.9 + plan §SIM-34：

**5 炼油专用字段**（ADD-001 §3.8-3.9）：
- rvp: Reid Vapor Pressure (psi)
- tvp: True Vapor Pressure (psi)
- watson_k: Watson characterization K-factor (UOP K)
- flash_point: 闪点 (°C)
- distillation_curves: JSONB 容器（spec V1.1 §变更 8 蒸馏曲线 8 种 schema）

**蒸馏曲线 8 种类型**（spec V1.1 §变更 8）：
- D86 (ASTM D86, 常压蒸馏)
- TBP (True Boiling Point, 真沸点蒸馏)
- EFV (Equilibrium Flash Vaporization, 平衡闪蒸)
- D86_CRACKING (D86 with cracking)
- D1160 (ASTM D1160, 减压蒸馏)
- D2887 (SimDist GC 模拟蒸馏)
- D5236 (ASTM D5236, 减压蒸馏高温)
- D7169 (ASTM D7169, 高温 SimDist)

每条曲线 schema：
    {
        "curve_type": "D86" | "TBP" | ...,
        "points": [{"percent_vapor": 0~100, "temp_c": float}, ...],
        "pressure_mmhg": float | None,
    }

down_revision = p3sim_streams_vapor_fields
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p3sim_streams_petroleum_fields"
down_revision = "p3sim_streams_vapor_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 4 个 Float 字段
    op.add_column(
        "streams",
        sa.Column(
            "rvp",
            sa.Float(),
            nullable=True,
            comment="SIM-34 §3.8: Reid Vapor Pressure psi",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "tvp",
            sa.Float(),
            nullable=True,
            comment="SIM-34 §3.8: True Vapor Pressure psi",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "watson_k",
            sa.Float(),
            nullable=True,
            comment="SIM-34 §3.8: Watson characterization K-factor (UOP K)",
        ),
    )
    op.add_column(
        "streams",
        sa.Column(
            "flash_point",
            sa.Float(),
            nullable=True,
            comment="SIM-34 §3.8: 闪点 °C",
        ),
    )
    # 蒸馏曲线 JSONB 容器
    op.add_column(
        "streams",
        sa.Column(
            "distillation_curves",
            JSONB(),
            nullable=True,
            comment="SIM-34 §3.9: 蒸馏曲线 8 种 schema（D86/TBP/EFV/D86_CRACKING/D1160/D2887/D5236/D7169）",
        ),
    )


def downgrade() -> None:
    op.drop_column("streams", "distillation_curves")
    op.drop_column("streams", "flash_point")
    op.drop_column("streams", "watson_k")
    op.drop_column("streams", "tvp")
    op.drop_column("streams", "rvp")