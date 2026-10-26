"""P9A-DLV-011 T2：`project_signature_matrix_bindings` 加 (project_id, module) 唯一约束。

## 为什么补这个约束（TODO-071 · bug-2052）

`ProjectSignatureMatrixBinding` 的 ORM 注释写着「一个项目同一模块只能绑定一个
矩阵」⇒ **但表上既没有这个唯一约束，ORM 也没声明**
（迁移 `dd47298c9c38` 只建了 PK + 两个普通索引）。

⇒ `SignatureMatrixService._ensure_binding` 只能靠「**先查后建**」保证幂等
⇒ **并发**下两个事务各建一行 ⇒ 同一项目同一模块绑到**两个**矩阵。

后果比「两个真相源」更硬：之后每次 `ensure_change_notice_matrix` 的
`scalar_one_or_none()` 会抛 **`MultipleResultsFound`** ⇒ 该项目的变更单路径
**永久 500**，直到人工清库。

⇒ 约束是这条路径的**唯一**兜底（应用层的先查后建挡不住并发）。

## 为什么不在迁移里**删掉**重复行

重复的绑定是**业务数据**（谁在什么时候把项目绑到了哪个矩阵）⇒ 静默删行
= 静默丢业务事实 ⇒ 本迁移遇到重复**响亮失败**并说清怎么办。

实测（2026-10-26，开发库 `pcs`）：`project_signature_matrix_bindings` **0 行**
⇒ 升级路径不会撞上这个失败分支；失败分支留给「别的库已被手工塞过数据」的情况。

## Revision

`revision = p9_008`，`down_revision = p9_007`（当前 head）。
"""
from __future__ import annotations

from alembic import op

revision = "p9_008"
down_revision = "p9_007"
branch_labels = None
depends_on = None

_CONSTRAINT = "uq_project_signature_matrix_bindings_project_module"
_TABLE = "project_signature_matrix_bindings"


def upgrade() -> None:
    """先查重（响亮失败）⇒ 再加唯一约束。"""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM {_TABLE}
                GROUP BY project_id, module HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    '{_TABLE} 存在 (project_id, module) 重复行；'
                    '请先人工清理（重复绑定会让同一项目同一模块绑到两个矩阵，'
                    '之后每次解析绑定都会 MultipleResultsFound）';
            END IF;
        END $$;
        """
    )
    op.create_unique_constraint(
        _CONSTRAINT,
        _TABLE,
        ["project_id", "module"],
    )


def downgrade() -> None:
    """删唯一约束。

    ⚠️ 降级后重新出现「先查后建」的并发窗口（应用层仍幂等，但并发不再被
    DB 挡住）—— 这是降级的固有代价，不在降级路径里修。
    """
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
