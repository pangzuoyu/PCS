"""P5-4 HEAT: duty 列拆分为 duty_legacy + duty_calc（ADR-0027 V1.0 决策 5).

按 ADR-0027 V1.0 决策 5 跟踪项（"P5-4 实施时按需拆分"）：
原 heat_results.duty 同时承载 9 旧 P4 上游值与 SUP-009 P5 计算结果，业务语义模糊。
本迁移加 2 列：

1. `duty_legacy` Float nullable — P4 上游 duty（即 heat_data_service._store 写入 inp.duty）
2. `duty_calc` Float nullable — P5 计算结果（即 htri.heat_duty_w）

**backfill 策略**：现有 heat_results.duty 默认按"溯源未知"处理，全部回填到 duty_calc
（多数 P5 数据由 HTRI parser 写入 duty_calc 路径）。duty_legacy 留空，由 HEAT
service 层新增写入逻辑补全（详见 app/services/heat/heat_data_service.py 同步修改）。

**不删原 `duty` 列**：向后兼容 P5-OPEN-006 §"9 旧标量"承诺 + 不阻断现有读取层。
后续若 P5-4 HEAT 全量切换至 duty_calc/duty_legacy 双轨，P5+ 后续批可下掉。

**DOWN-REVISION** = p4_4_sim_import_preview_towers（p3.2-sim branch head）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p5_4_heat_duty_split"
down_revision = "p4_4_sim_import_preview_towers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """heat_results.duty 拆分为 duty_legacy + duty_calc（P5-4 HEAT / ADR-0027 V1.0 决策 5).

    步骤：
    - A. 加 duty_legacy Float NULL：P4 上游 duty（heat_data_service._store 写入 inp.duty）
    - B. 加 duty_calc Float NULL：P5 计算结果（htri.heat_duty_w）
    - C. 存量回填：duty IS NOT NULL 行 → duty_calc（多数 P5 数据由 HTRI parser 写入）
    - D. duty_legacy 留空（无法判断原值溯源，由 HEAT service 层新增写入补全）

    不删原 duty 列：向后兼容 P5-OPEN-006 §"9 旧标量"承诺 + 不阻断现有读取层。
    后续 P5+ 批若全量切换至双轨可下掉 duty 列。

    业务：ADR-0027 V1.0 决策 5 跟踪项落地 — 原 duty 同时承载 P4 上游与 P5
    计算结果业务语义模糊，拆分后溯源清晰。
    """
    # 1. 加 duty_legacy 列（P4 上游 duty；可空）
    op.add_column(
        "heat_results",
        sa.Column("duty_legacy", sa.Float(), nullable=True),
    )

    # 2. 加 duty_calc 列（P5 计算 duty；可空）
    op.add_column(
        "heat_results",
        sa.Column("duty_calc", sa.Float(), nullable=True),
    )

    # 3. 存量回填：duty IS NOT NULL 的行 → duty_calc（默认按 P5 计算结果归属）
    #    duty_legacy 留空（无法判断原值是 P4 上游还是 P5 计算）
    op.execute(
        "UPDATE heat_results SET duty_calc = duty WHERE duty IS NOT NULL"
    )


def downgrade() -> None:
    """heat_results.duty 拆字段逆向（P5-4 HEAT duty 拆分回滚).

    步骤：
    - UPDATE duty 兜底回填：duty_legacy 与 duty_calc 任一非空 → 写回 duty
    - DROP COLUMN heat_results.duty_calc
    - DROP COLUMN heat_results.duty_legacy

    业务：与 upgrade 互逆；duty 拆 duty_legacy + duty_calc 之前先做兜底回填
    （避免 duty NULL 行被丢掉），本迁移是 P5-4 HEAT duty 拆分回滚安全网。
    """
    # 回填 duty 兜底：duty_legacy 与 duty_calc 任一非空 → 写回 duty
    op.execute(
        "UPDATE heat_results "
        "SET duty = COALESCE(duty_legacy, duty_calc) "
        "WHERE duty IS NULL AND (duty_legacy IS NOT NULL OR duty_calc IS NOT NULL)"
    )
    op.drop_column("heat_results", "duty_calc")
    op.drop_column("heat_results", "duty_legacy")