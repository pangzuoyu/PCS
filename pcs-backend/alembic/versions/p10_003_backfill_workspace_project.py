"""p10_003：回填 `workspaces.project_id`（P10-F 评审的 P0 修 · 2026-11-18）

## 为什么

「FORMAL 工作区恰好属于一个项目，无项目的工作区是 PERSONAL」（人裁决 2026-11-18 ·
TODO-169）⇒ ⇒ 这条绑定**必须由生产路径建立起来**。

⚠️ **此前没有生产路径建立它**：`POST /projects` 只写
`Project(workspace_id=...)`，**从不回填** `workspace.project_id`
⇒ ⇒ 那列在真实库里**恒为 NULL** ⇒ ⇒
`app/services/workspace_service.py::require_workspace_access_or_404`
若拿它当分档键 ⇒ ⇒ **把 FORMAL 工作区当成 PERSONAL** ⇒ ⇒
① 项目的其他成员（有 `user_projects` 授权行）读管路记录 ⇒ **404**；
② `POST /records/piping` ⇒ ⇒ **恒 400**（写入路径整条死掉）。

⇒ ⇒ 只有**种子脚本**（`scripts/seed_e2e_flows.py`）会回填 ⇒ ⇒
**E2E 车道造的是生产不存在的形状** ⇒ ⇒ 「替身比被测物更宽容」。

## 做什么

把「工作区实际挂的项目」（`projects.workspace_id`）**回填**进
`workspaces.project_id` ⇒ ⇒ 让存量数据与新代码的读法一致。

⚠️ **只处理「恰好挂一个项目」的工作区**：挂两个 ⇒ 违反 1:1 ⇒
**不猜**（`min()` 会挑一个 ⇒ 可能与授权对不上）⇒ ⇒ 留给运行时的
`WORKSPACE_PROJECT_AMBIGUOUS`（409）fail-loud 指出去修。

⚠️ **本迁移只改数据，不改 schema** ⇒ ⇒ ORM 侧**无需同步**（列早就在）。

## 幂等

重复跑：条件是 `w.project_id IS DISTINCT FROM p.project_id`
⇒ ⇒ 第二遍没有行可改 ⇒ ⇒ 不炸、不重复改。
"""
from __future__ import annotations

from alembic import op

revision = "p10_003"
down_revision = "p10_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ⚠️ `IS DISTINCT FROM`（不是 `<>`）⇒ ⇒ NULL 也算「不同」⇒ ⇒ 能填 NULL。
    # ⚠️ **不用 `min(uuid)`** ⇒ ⇒ PG **没有** uuid 的聚合函数（实测报
    #    `function min(uuid) does not exist`）⇒ ⇒ 改成「直接 JOIN + count 守卫」
    #    ⇒ ⇒ `count(*) = 1` 保证 JOIN 只命中一行 ⇒ ⇒ 不需要挑。
    op.execute(
        """
        UPDATE workspaces w
        SET project_id = p.project_id
        FROM projects p
        WHERE p.workspace_id = w.workspace_id
          AND w.project_id IS DISTINCT FROM p.project_id
          AND (
            SELECT count(*) FROM projects p2
            WHERE p2.workspace_id = w.workspace_id
          ) = 1
        """
    )


def downgrade() -> None:
    # 迁移前的生产状态 = 「工作区上没有 project_id」⇒ ⇒ 还原成 NULL。
    # ⚠️ 只还原**与该工作区实际挂的项目相同**的那些行 ⇒ ⇒ 不碰人工填的值。
    op.execute(
        """
        UPDATE workspaces w
        SET project_id = NULL
        FROM projects p
        WHERE p.workspace_id = w.workspace_id
          AND w.project_id = p.project_id
          AND (
            SELECT count(*) FROM projects p2
            WHERE p2.workspace_id = w.workspace_id
          ) = 1
        """
    )
