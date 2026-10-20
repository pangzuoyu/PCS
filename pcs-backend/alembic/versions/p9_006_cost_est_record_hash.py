"""P9A-4 D0：cost_est_results 补 record_hash（并发令牌）+ 回填。

## 为什么只补这一张表

29 张 `*_result(s)` 表里，`cost_est_results` 是**唯一「可编辑 ∧ 无任何并发
令牌」**的表（`PATCH /results/{id}`，且**无 sign_status 门禁** ⇒ 所有状态可
PATCH）。其余 25 张已有 `record_hash`；`util_results` / `sim_*`(8) /
`two_phase_results` **无手动编辑端点** —— 没有编辑场景，并发保护保护的是一个
不存在的并发。详见 ADR-0048 §⑥ 的收窄表。

⚠️ **不引入 `row_version`** —— 会造第二套并发令牌。

## 列形状：String(64) NOT NULL default ''

与全库另外 **25 张** `record_hash` 列**完全同形**（`RecordMixin.record_hash`
声明 `app/models/mixins.py:61`；初始 schema `dd47298c9c38`；给
`two_phase_results` 补列的先例 `p4_task0_lineage_extension`）。

- **64 不是 16**：16 是**值**的长度（`calc_lineage._HASH_PREFIX`），不是列宽；
  SHA-256 完整 hex 恰好 64 字符 ⇒ 64 是有意的余量。计划原文写的
  `String(16)` 会造出第 26 张**异形**表。
- **NOT NULL 不是 nullable**：空串是「未计算」的唯一哨兵，ADR-0048 §⑥ 的
  退化阶梯就是按 `record_hash == ""` 分支写的；用 NULL 会让阶梯漏判。

## 回填为什么在迁移里做（而不是「记得手工跑一次脚本」）

本仓吃过「守门没跑却看着是绿的」亏（`alembic check` 在 DB 落后 code head 时
exit 0 但根本没跑）。升级路径必须自带回填，不能依赖人记得执行。

⚠️ 回填**复用 app 侧唯一的哈希实现**（`calc_lineage.compute_record_hash`），
**不在迁移里复制第二份算法** —— 同一概念两份清单必然漂移（TODO-058 裁决）。

## Revision

`revision = p9_006`，`down_revision = p9_005`。
⚠️ 计划原文写 `p9_004` —— 那个号已被 `p9_004_record_comments_type_width`
占用，当前 head 是 `p9_005`。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p9_006"
down_revision = "p9_005"
branch_labels = None
depends_on = None


def _backfill_record_hash() -> int:
    """按当前内容回填 `cost_est_results.record_hash`（幂等）。返回处理行数。

    ⚠️ 复用 `app.services.calc_lineage.apply_record_hash`（它调
    `compute_record_hash`）—— **单一来源**，迁移里不复制哈希算法。
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models.calc import CostEstResult
    from app.services.calc_lineage import apply_record_hash

    conn = op.get_bind()
    # ⚠️ Session 复用 alembic 的连接：外部事务已开启 ⇒ session 走 SAVEPOINT，
    # `commit()` 只释放 savepoint（数据留在 alembic 的事务里，由 alembic 提交）。
    session = Session(bind=conn)
    try:
        rows = session.execute(select(CostEstResult)).scalars().all()
        n = apply_record_hash(rows)
        session.commit()
        return n
    finally:
        session.close()


def upgrade() -> None:
    """加列 + 回填存量行。

    步骤：
    - A. `cost_est_results` 加 1 列：record_hash String(64) NOT NULL default ''
    - B. 回填：按当前内容重算 hash（幂等；空串 = 未计算 ⇒ 回填后不再是空串）
    """
    op.add_column(
        "cost_est_results",
        sa.Column(
            "record_hash",
            sa.String(64),
            nullable=False,
            server_default="",
            comment="SHA-256 截断 16 hex；与 RecordMixin 同语义（P9A-4 D0 扩展）",
        ),
    )
    _backfill_record_hash()


def downgrade() -> None:
    """删列（数据丢失：回填出来的 hash 无法恢复）。

    步骤：
    - DROP COLUMN cost_est_results.record_hash
    """
    op.drop_column("cost_est_results", "record_hash")
