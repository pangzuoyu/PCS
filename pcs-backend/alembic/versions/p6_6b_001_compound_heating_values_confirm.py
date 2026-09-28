"""P6-6B T1: ``compound_heating_values`` process metadata 闭环（OPEN-P6-4-1）。

P6-4 阶段工艺工程师已抄录 64 种化合物 HHV/LHV/MW（GPSA FIG. 23-2 +
API 5B6 公开值），当时落库使用 ``source='SYNTHETIC_TEST_DATA'`` +
``confirmed_by='PLACEHOLDER'`` 占位；本迁移按 P6-6B 闭环裁决将占位
标记替换为正式来源标记：

- ``source='GPSA FIG. 23-2 (2022) + API 5B6'``
- ``confirmed_by='P6-6B_ENG_TEAM'``
- ``confirmed_at='2026-09-28'``

范围：

1. **不**修改 ORM 模型（``app/models/config.py:CompoundHeatingValues``）。
2. **不**修改 P6-4 seed 脚本；本迁移运行后该脚本二次执行仍能 DELETE
   并重新 INSERT 64 行（届时 ``source='SYNTHETIC_TEST_DATA'``，需 P6-6B
   重跑本迁移即可再次闭环）。
3. **不**重抄 HHV/LHV/MW 数值（P6-4 阶段已与 GPSA FIG. 23-2 (2022 ed.)
   + API 5B6 一致性核对）。
4. 仅对 ``source='SYNTHETIC_TEST_DATA'`` 行做 UPDATE；其他来源行不动。

OPEN-P6-4-1 关闭。

DOWN-REVISION = ``p6_5_006_orm_db_drift_final_fix``（P6-5 末态 alembic
head；2026-09-25 由 P6-5 Task 提交）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_6b_001_compound_heating_values_confirm"
down_revision = "p6_5_006_orm_db_drift_final_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """UPDATE 64 行 ``compound_heating_values`` 的 metadata 字段。

    仅匹配 ``source='SYNTHETIC_TEST_DATA'``；其他来源行不动。
    一次性 UPDATE（同 PG 事务原子），配合 ``confirmed_at`` 设固定日期
    （2026-09-28）便于审计追溯。
    """
    op.execute(
        "UPDATE compound_heating_values "
        "SET source = 'GPSA FIG. 23-2 (2022) + API 5B6', "
        "    confirmed_by = 'P6-6B_ENG_TEAM', "
        "    confirmed_at = '2026-09-28' "
        "WHERE source = 'SYNTHETIC_TEST_DATA'"
    )


def downgrade() -> None:
    """还原为占位 metadata（互逆于 upgrade）。

    仅匹配本迁移升级过的行（即 ``source='GPSA FIG. 23-2 (2022) + API 5B6'``
    且 ``confirmed_by='P6-6B_ENG_TEAM'``），不影响后续工艺工程师签字过的
    真实期号行。
    """
    op.execute(
        "UPDATE compound_heating_values "
        "SET source = 'SYNTHETIC_TEST_DATA', "
        "    confirmed_by = 'PLACEHOLDER', "
        "    confirmed_at = NULL "
        "WHERE source = 'GPSA FIG. 23-2 (2022) + API 5B6' "
        "  AND confirmed_by = 'P6-6B_ENG_TEAM'"
    )
