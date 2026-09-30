"""P6-6B T5: ``compound_api521_thresholds`` process metadata 闭环（C-21 fire case 阈值).

P6-5 阶段工艺工程师已抄录 2 行 API 521 (2020) §3.4 + AS 1210 §4.4
致死/致伤辐射热通量阈值（``INJURY`` 4.7 kW/m² / ``LETHALITY`` 12.6 kW/m²），
当时落库使用 ``source='SYNTHETIC_TEST_DATA'`` + ``confirmed_by='工艺室_占位'``
占位；本迁移按 P6-6B 闭环裁决将占位标记替换为正式来源标记：

- ``source='API 521 (2020) §3.4 + AS 1210 §4.4'``
- ``confirmed_by='P6-6B_ENG_TEAM'``
- ``confirmed_at='2026-09-28'``

范围：

1. **不**修改 ORM 模型（``app/models/config.py:CompoundApi521Thresholds``）。
2. **不**修改 P6-5 seed 脚本（``scripts/p6_5_seed_api521_thresholds.py``）；
   本迁移运行后该脚本二次执行仍能 DELETE 并重新 INSERT 2 行（届时
   ``source='SYNTHETIC_TEST_DATA'``，需 P6-6B 重跑本迁移即可再次闭环）。
3. **不**重抄 ``flux_kw_m2`` 数值（P6-5 阶段已与 API 521 (2020) §3.4 +
   AS 1210 §4.4 原文一致性核对）。
4. 仅对 ``source='SYNTHETIC_TEST_DATA'`` 行做 UPDATE；其他来源行不动。

OPEN-P6-6A-5 部分关闭（ΔH_vap 口径仍待 T12 关闭）。
T13 C-21 测试 fire_case coefficient 来源标记验收。

DOWN-REVISION = ``p6_6b_004_pasquill_sigma_confirm``（P6-6B T4；2026-09-28
由 P6-6B Task 4 提交）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_6b_005_api521_thresholds_confirm"
down_revision = "p6_6b_004_pasquill_sigma_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """UPDATE 2 行 ``compound_api521_thresholds`` 的 metadata 字段.

    仅匹配 ``source='SYNTHETIC_TEST_DATA'``；其他来源行不动。
    一次性 UPDATE（同 PG 事务原子），配合 ``confirmed_at`` 设固定日期
    （2026-09-28）便于审计追溯。
    """
    op.execute(
        "UPDATE compound_api521_thresholds "
        "SET source = 'API 521 (2020) §3.4 + AS 1210 §4.4', "
        "    confirmed_by = 'P6-6B_ENG_TEAM', "
        "    confirmed_at = '2026-09-28' "
        "WHERE source = 'SYNTHETIC_TEST_DATA'"
    )


def downgrade() -> None:
    """还原为占位 metadata（互逆于 upgrade).

    仅匹配本迁移升级过的行（即 ``source='API 521 (2020) §3.4 + AS 1210
    §4.4'`` 且 ``confirmed_by='P6-6B_ENG_TEAM'``），不影响后续工艺工程师
    签字过的真实期号行。

    注意：``confirmed_by`` 还原为 ``'PLACEHOLDER'``（brief 指定），可能与
    历史 pcs dev 库中预存的 ``'工艺室_占位'`` 不一致；P6-5 seed 脚本二次执行
    会 DELETE 并重新 INSERT，再次跑本迁移即可再次闭环。
    """
    op.execute(
        "UPDATE compound_api521_thresholds "
        "SET source = 'SYNTHETIC_TEST_DATA', "
        "    confirmed_by = 'PLACEHOLDER', "
        "    confirmed_at = NULL "
        "WHERE source = 'API 521 (2020) §3.4 + AS 1210 §4.4' "
        "  AND confirmed_by = 'P6-6B_ENG_TEAM'"
    )
