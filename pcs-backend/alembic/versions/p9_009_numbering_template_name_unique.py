"""P9A-DLV-011 收官批：`numbering_templates.template_name` 加唯一约束（TODO-073）。

## 为什么补这个约束

变更单的编号改走**编号模板**（可读编号 `{项目号}-CHANGE_NOTICE-{序号}`）⇒
内置模板是「**先查后建**」（按 `template_name` 找，找不到才建）⇒
**并发**下两个事务各建一份模板 ⇒ 两个不同的 `template_id`。

后果比「模板表多一行」更硬：两份模板 ⇒ **两条独立的号段** ⇒ 同一个项目里
出现**两个 1、两个 2 …** ⇒ 两个变更单**对外同号** ⇒ 凭证认不出是哪一张。

⇒ `template_name` 必须**全局唯一** ⇒ 它是这条路径的**唯一**兜底
（应用层的「先查后建」挡不住并发 —— 与 `p9_008` 同理）。

## 为什么不在迁移里**删掉**重复行

重复的模板是**配置数据**（谁在什么时候建了哪张模板）⇒ 静默删行 = 静默丢
配置事实 ⇒ 本迁移遇到重复**响亮失败**并说清怎么办。

实测（2026-10-27，开发库 `pcs` 与 `pcs_test`）：`numbering_templates` **0 行**
⇒ 升级路径不会撞上这个失败分支；失败分支留给「别的库已被手工塞过数据」的
情况。

## Revision

`revision = p9_009`，`down_revision = p9_008`（当前 head）。
"""
from __future__ import annotations

from alembic import op

revision = "p9_009"
down_revision = "p9_008"
branch_labels = None
depends_on = None

_CONSTRAINT = "uq_numbering_templates_template_name"
_TABLE = "numbering_templates"


def upgrade() -> None:
    """先查重（响亮失败）⇒ 再加唯一约束。"""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM {_TABLE}
                GROUP BY template_name HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    '{_TABLE} 存在 template_name 重复行；'
                    '请先人工清理（重复模板 ⇒ 两条独立号段 ⇒ 同一项目里会出现'
                    '两个同号的变更单，凭证认不出是哪一张）';
            END IF;
        END $$;
        """
    )
    op.create_unique_constraint(_CONSTRAINT, _TABLE, ["template_name"])


def downgrade() -> None:
    """删唯一约束。

    ⚠️ 降级后重新出现「先查后建」的并发窗口（应用层仍幂等，但并发不再被
    DB 挡住）—— 这是降级的固有代价，不在降级路径里修。
    """
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
