"""P9A-DLV-011 收官批：`signature_matrices` 加 (matrix_name, status) 唯一约束（TODO-074）。

## 为什么补这个约束

`SignatureMatrixService._get_or_create_builtin_matrix` 按
`(matrix_name, status='ACTIVE')` **找第一份** ⇒ **并发**下两个事务各建一份
⇒ 同名的 ACTIVE 矩阵有**两份**。

后果：两个项目可能绑到**不同的一份** ⇒「谁该签这一步」出现**两个答案**
⇒ 同一项目里同一条记录，按不同人查出来的签署链**不一样**。

⇒ 约束是这条路径的**唯一**兜底（应用层的「先查后建」挡不住并发 —— 与
`p9_008` 同理）。

## 为什么约束是 **(matrix_name, status)** 而不是「名字全局唯一」

一份**已作废**（OBSOLETE）的同名模板不该**永久堵住**重建 ⇒ 否则作废后再也
建不出同名的 ACTIVE 模板 ⇒ 运维只能改名字 ⇒ 历史绑定里的旧名字全是死链。

⇒ 同一**状态**下名字唯一就够 —— 而这正是应用层 `_assert_name_free` 的判定
口径（应用层与 DB 约束**同口径** ⇒ 409 与 500 的分界一致）。

## 为什么不在迁移里**删掉**重复行

重复的矩阵是**业务数据**（谁在什么时候建了哪张矩阵、绑了哪些项目）⇒ 静默删
行 = 静默丢业务事实 ⇒ 本迁移遇到重复**响亮失败**并说清怎么办。

实测（2026-10-27，开发库 `pcs` 与 `pcs_test`）：`signature_matrices` **0 行**
⇒ 升级路径不会撞上这个失败分支；失败分支留给「别的库已被手工塞过数据」的
情况。

## Revision

`revision = p9_010`，`down_revision = p9_009`（当前 head）。
"""
from __future__ import annotations

from alembic import op

revision = "p9_010"
down_revision = "p9_009"
branch_labels = None
depends_on = None

_CONSTRAINT = "uq_signature_matrices_name_status"
_TABLE = "signature_matrices"


def upgrade() -> None:
    """先查重（响亮失败）⇒ 再加唯一约束。"""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM {_TABLE}
                GROUP BY matrix_name, status HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    '{_TABLE} 存在 (matrix_name, status) 重复行；'
                    '请先人工清理（同名同状态的两份矩阵 ⇒ 两个项目可能绑到不同的'
                    '一份 ⇒ 同一条记录的签署链出现两个答案）';
            END IF;
        END $$;
        """
    )
    op.create_unique_constraint(
        _CONSTRAINT,
        _TABLE,
        ["matrix_name", "status"],
    )


def downgrade() -> None:
    """删唯一约束。

    ⚠️ 降级后重新出现「先查后建」的并发窗口（应用层仍幂等，但并发不再被
    DB 挡住）—— 这是降级的固有代价，不在降级路径里修。
    """
    op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")
