"""P6-6B T7: ``compound_hammerschmidt_K`` process metadata 闭环（C-18 水合物抑制）。

P6-5 阶段工艺工程师已抄录 5 行 Hammerschmidt 1934 OG + Nielsen 1988 +
GPSA Fig. 20-XX 温降常数（``MEOH=2335 / EG=2220 / DEG=2335 /
TEG=2500 / NACL=1297``），当时落库使用 ``source='SYNTHETIC_TEST_DATA'``
+ ``confirmed_by='PLACEHOLDER'`` 占位；本迁移按 P6-6B 闭环裁决将占位
标记替换为正式来源标记：

- ``source='Hammerschmidt 1934 OG / Nielsen 1988 / GPSA Fig. 20-XX'``
- ``confirmed_by='P6-6B_ENG_TEAM'``
- ``confirmed_at='2026-09-28'``

范围：

1. **不**修改 ORM 模型（``app/models/config.py:CompoundHammerschmidtK``）。
2. **不**修改 P6-5 seed 脚本（``scripts/p6_5_seed_hammerschmidt_K.py``）；
   本迁移运行后该脚本二次执行仍能 DELETE 并重新 INSERT 5 行（届时
   ``source='SYNTHETIC_TEST_DATA'``，需 P6-6B 重跑本迁移即可再次闭环）。
3. **不**重抄 ``K`` 数值（P6-5 阶段已与 Hammerschmidt 1934 OG
   + Nielsen 1988 + GPSA Fig. 20-XX 原文一致性核对）。
4. 仅对 ``source='SYNTHETIC_TEST_DATA'`` 行做 UPDATE；其他来源行不动。

OPEN-P6-6A-3 部分关闭（C-18 水合物抑制 metadata 闭环；T10 K_F→K_C
service 集成推迟到 Phase 2）。

DOWN-REVISION = ``p6_6b_006_iso9613_confirm``（P6-6B T6；2026-09-28
由 P6-6B Task 6 提交）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_6b_007_hammerschmidt_K_confirm"
down_revision = "p6_6b_006_iso9613_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """UPDATE 5 行 ``compound_hammerschmidt_K`` 的 metadata 字段。

    仅匹配 ``source='SYNTHETIC_TEST_DATA'``；其他来源行不动。
    一次性 UPDATE（同 PG 事务原子），配合 ``confirmed_at`` 设固定日期
    （2026-09-28）便于审计追溯。

    注意：表名带大写 ``K``（``__tablename__ = "compound_hammerschmidt_K"``），
    PG 折叠规则下需双引号包裹；否则会被错误解释为
    ``compound_hammerschmidt_k`` 而报 UndefinedTable。
    """
    op.execute(
        'UPDATE "compound_hammerschmidt_K" '
        "SET source = 'Hammerschmidt 1934 OG / Nielsen 1988 / GPSA Fig. 20-XX', "
        "    confirmed_by = 'P6-6B_ENG_TEAM', "
        "    confirmed_at = '2026-09-28' "
        "WHERE source = 'SYNTHETIC_TEST_DATA'"
    )


def downgrade() -> None:
    """还原为占位 metadata（互逆于 upgrade）。

    仅匹配本迁移升级过的行（即 ``source='Hammerschmidt 1934 OG /
    Nielsen 1988 / GPSA Fig. 20-XX'`` 且 ``confirmed_by='P6-6B_ENG_TEAM'``），
    不影响后续工艺工程师签字过的真实期号行。

    注意：``confirmed_by`` 还原为 ``'PLACEHOLDER'``（brief 指定）；P6-5 seed
    脚本二次执行会 DELETE 并重新 INSERT，再次跑本迁移即可再次闭环。

    表名带大写 ``K`` 同 upgrade，须双引号包裹。
    """
    op.execute(
        'UPDATE "compound_hammerschmidt_K" '
        "SET source = 'SYNTHETIC_TEST_DATA', "
        "    confirmed_by = 'PLACEHOLDER', "
        "    confirmed_at = NULL "
        "WHERE source = 'Hammerschmidt 1934 OG / Nielsen 1988 / GPSA Fig. 20-XX' "
        "  AND confirmed_by = 'P6-6B_ENG_TEAM'"
    )