"""P6-6B T4: ``compound_pasquill_sigma`` process metadata 闭环（C-22 大气扩散）。

P6-5 阶段工艺工程师已抄录 6 行 Pasquill-Gifford 稳定度系数
(``a_y``/``b_y``/``a_z``/``b_z``；Briggs 1973 open terrain)，当时落库使用
``source='SYNTHETIC_TEST_DATA'`` + ``confirmed_by='PLACEHOLDER'``
（或 '工艺室_占位'，pcs dev 库历史值）占位；本迁移按 P6-6B 闭环裁决
将占位标记替换为正式来源标记：

- ``source='EPA ISC3 (1995) User's Guide + Briggs (1973)'``
- ``confirmed_by='P6-6B_ENG_TEAM'``
- ``confirmed_at='2026-09-28'``

范围：

1. **不**修改 ORM 模型（``app/models/config.py:CompoundPasquillSigma``）。
2. **不**修改 P6-5 seed 脚本；本迁移运行后该脚本二次执行仍能 DELETE
   并重新 INSERT 6 行（届时 ``source='SYNTHETIC_TEST_DATA'``，需 P6-6B
   重跑本迁移即可再次闭环）。
3. **不**重抄 ``a_y``/``b_y``/``a_z``/``b_z`` 数值（P6-5 阶段已与 EPA ISC3
   (1995) User's Guide + Briggs (1973) 原文一致性核对）。
4. 仅对 ``source='SYNTHETIC_TEST_DATA'`` 行做 UPDATE；其他来源行不动。

OPEN-P6-4-2 关闭（C-22 大气扩散闭环）。

DOWN-REVISION = ``p6_6b_003_pipe_e_modulus``（P6-6B T3；2026-09-28
由 P6-6B Task 3 提交）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_6b_004_pasquill_sigma_confirm"
down_revision = "p6_6b_003_pipe_e_modulus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """UPDATE 6 行 ``compound_pasquill_sigma`` 的 metadata 字段。

    仅匹配 ``source='SYNTHETIC_TEST_DATA'``；其他来源行不动。
    一次性 UPDATE（同 PG 事务原子），配合 ``confirmed_at`` 设固定日期
    （2026-09-28）便于审计追溯。
    """
    op.execute(
        "UPDATE compound_pasquill_sigma "
        "SET source = 'EPA ISC3 (1995) User''s Guide + Briggs (1973)', "
        "    confirmed_by = 'P6-6B_ENG_TEAM', "
        "    confirmed_at = '2026-09-28' "
        "WHERE source = 'SYNTHETIC_TEST_DATA'"
    )


def downgrade() -> None:
    """还原为占位 metadata（互逆于 upgrade）。

    仅匹配本迁移升级过的行（即 ``source='EPA ISC3 (1995) User's Guide +
    Briggs (1973)'`` 且 ``confirmed_by='P6-6B_ENG_TEAM'``），不影响后续
    工艺工程师签字过的真实期号行。

    注意：``confirmed_by`` 还原为 ``'PLACEHOLDER'``（brief 指定），可能与
    历史 pcs dev 库中预存的 ``'工艺室_占位'`` 不一致；P6-5 seed 脚本二次执行
    会 DELETE 并重新 INSERT，再次跑本迁移即可再次闭环。
    """
    op.execute(
        "UPDATE compound_pasquill_sigma "
        "SET source = 'SYNTHETIC_TEST_DATA', "
        "    confirmed_by = 'PLACEHOLDER', "
        "    confirmed_at = NULL "
        "WHERE source = 'EPA ISC3 (1995) User''s Guide + Briggs (1973)' "
        "  AND confirmed_by = 'P6-6B_ENG_TEAM'"
    )
