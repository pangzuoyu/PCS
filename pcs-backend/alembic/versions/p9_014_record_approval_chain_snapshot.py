"""给全部记录表加 `approval_chain_snapshot`（P9B-2 评审 #1 · 委员会裁决：快照）。

## 为什么

`submit-approval` 的批准链此前在**中间步骤**回查实时矩阵
（`_next_approval_role` → `resolve_project_matrix`）⇒ 两个洞：

1. **中途重绑矩阵可绕过自审禁令**（CWE-863）：提交时链里没有自己的角色
   （自审过关）⇒ 提交后把项目重绑到「含自己角色」的矩阵 ⇒ 第 2 步起
   轮到自己批自己；
2. **矩阵中途被禁用 ⇒ 链卡死**（409 `SIGNATURE_MATRIX_NOT_ACTIVE`）
   —— 已提交的记录被**后来的配置变更**劫持。

交付物侧同类问题早已用快照修掉（`deliverable_service._steps_for_version`）；
记录侧照做：**submit 时把链冻进记录行**，中间步骤只读快照。

## 列形状（与 ORM `RecordMixin.approval_chain_snapshot` 一致）

`JSONB / nullable`：`{matrix_id, steps: [{step_order, sign_role}],
submitted_by, submitted_by_role}`。nullable 是有意的：
- 存量 IN_APPROVAL 行没有快照 ⇒ 读路径对 `IS NULL` 回退到实时矩阵
  （部署窗口兼容，行为不劣于修前）；
- 非 9 态生命周期的行永远为 NULL。

## ⚠️ bug-143 教训：mixin 列必须落**全**所有表

清单从 ORM 元数据反查（`RecordMixin` 的叶子子类），**硬编码**在下面 ——
不 import 应用模型（迁移自包含）。漏表 ⇒ `alembic check` 立刻报漂移（红），
单测（从 metadata 建表）**不会**红 —— 这正是 CLAUDE.md「漂移盲区」。

## Revision

`revision = p9_014`，`down_revision = p9_013`（当前 head）。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p9_014"
down_revision = "p9_013"
branch_labels = None
depends_on = None

_COLUMN = "approval_chain_snapshot"

#: 全部 RecordMixin 消费表（20 张；与 ORM 元数据一致，新增记录表时在此追加）
_TABLES = (
    "flash_results",
    "piping_results",
    "pipe_network_results",
    "pump_results",
    "psv_results",
    "flare_system_results",
    "vessel_results",
    "relief_results",
    "column_sizing",
    "mixer_results",
    "sep_equip_results",
    "heat_results",
    "cv_results",
    "restriction_results",
    "cooling_tower_results",
    "psychro_results",
    "open_channel_results",
    "filtration_results",
    "thermosiphon_circulation_results",
    "equipment_list",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column(_COLUMN, JSONB(), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, _COLUMN)
