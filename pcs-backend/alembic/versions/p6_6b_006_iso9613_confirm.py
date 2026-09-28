"""P6-6B T6: ``compound_iso9613_atmospheric_absorption`` process metadata 闭环
（C-22/C-23 大气吸收/噪声衰减）。

P6-5 阶段工艺工程师已抄录 4 行 ISO 9613-2 (1996) 大气吸收系数
（``temperature_c`` × ``humidity_pct`` → ``alpha_db_km``；10/15/20/25°C ×
50% RH 标准工况），当时落库使用 ``source='SYNTHETIC_TEST_DATA'`` +
``confirmed_by='工艺室_占位'``（pcs dev 库历史值）占位；本迁移按 P6-6B
闭环裁决将占位标记替换为正式来源标记：

- ``source='ISO 9613-2 (1996)'``
- ``confirmed_by='P6-6B_ENG_TEAM'``
- ``confirmed_at='2026-09-28'``

范围：

1. **不**修改 ORM 模型（``app/models/config.py:CompoundIso9613AtmosphericAbsorption``）。
2. **不**修改 P6-5 seed 脚本（``scripts/p6_5_seed_iso9613_atmospheric_absorption.py``）；
   本迁移运行后该脚本二次执行仍能 DELETE 并重新 INSERT 4 行（届时
   ``source='SYNTHETIC_TEST_DATA'``，需 P6-6B 重跑本迁移即可再次闭环）。
3. **不**重抄 ``alpha_db_km`` 数值（P6-5 阶段已与 ISO 9613-2 (1996)
   §3/§5 + Annex 原文一致性核对）。
4. 仅对 ``source='SYNTHETIC_TEST_DATA'`` 行做 UPDATE；其他来源行不动。

OPEN-P6-4-2 部分关闭（C-22 大气扩散闭环由 T4 完成；本批关闭噪声
衰减 4 行 metadata 闭环）。

DOWN-REVISION = ``p6_6b_005_api521_thresholds_confirm``（P6-6B T5；2026-09-28
由 P6-6B Task 5 提交）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_6b_006_iso9613_confirm"
down_revision = "p6_6b_005_api521_thresholds_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """UPDATE 4 行 ``compound_iso9613_atmospheric_absorption`` 的 metadata 字段。

    仅匹配 ``source='SYNTHETIC_TEST_DATA'``；其他来源行不动。
    一次性 UPDATE（同 PG 事务原子），配合 ``confirmed_at`` 设固定日期
    （2026-09-28）便于审计追溯。
    """
    op.execute(
        "UPDATE compound_iso9613_atmospheric_absorption "
        "SET source = 'ISO 9613-2 (1996)', "
        "    confirmed_by = 'P6-6B_ENG_TEAM', "
        "    confirmed_at = '2026-09-28' "
        "WHERE source = 'SYNTHETIC_TEST_DATA'"
    )


def downgrade() -> None:
    """还原为占位 metadata（互逆于 upgrade）。

    仅匹配本迁移升级过的行（即 ``source='ISO 9613-2 (1996)'`` 且
    ``confirmed_by='P6-6B_ENG_TEAM'``），不影响后续工艺工程师签字过的
    真实期号行。

    注意：``confirmed_by`` 还原为 ``'PLACEHOLDER'``（brief 指定），可能与
    历史 pcs dev 库中预存的 ``'工艺室_占位'`` 不一致；P6-5 seed 脚本二次执行
    会 DELETE 并重新 INSERT，再次跑本迁移即可再次闭环。
    """
    op.execute(
        "UPDATE compound_iso9613_atmospheric_absorption "
        "SET source = 'SYNTHETIC_TEST_DATA', "
        "    confirmed_by = 'PLACEHOLDER', "
        "    confirmed_at = NULL "
        "WHERE source = 'ISO 9613-2 (1996)' "
        "  AND confirmed_by = 'P6-6B_ENG_TEAM'"
    )