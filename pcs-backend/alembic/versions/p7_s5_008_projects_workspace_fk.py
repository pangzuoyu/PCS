"""p7_s5_008: 补 projects.workspace_id 外键 —— ORM 用 use_alter 声明，DB 侧从未建成.

ORM（`app/models/project.py:73`）把这一列声明成
`ForeignKey(..., use_alter=True, name="fk_projects_workspace_id")`，用来破解
`projects ↔ workspaces` 的循环依赖 —— `use_alter` 的语义是「**由一条
`ALTER TABLE ADD CONSTRAINT` 迁移单独创建**」，而不是让 SQLAlchemy 把它塞进
`CREATE TABLE`。写这份延迟迁移的那一步始终没有落地，于是 `projects` 表上
**一个外键约束都没有**（`pg_constraint` 查询返回空）。

后果：删掉一个工作区不会、也无从级联，项目会静默变成孤儿行。
`alembic check` 长期把它报成 `add_fk`（bug-146）。

`op.create_foreign_key` 发出的正是 `ALTER TABLE ... ADD CONSTRAINT`，所以迁移
里不需要 `use_alter`。先 drop 后 create 天然幂等：重跑会先删掉已存在的同名
约束再重建。
"""
from __future__ import annotations

from alembic import op

revision = "p7_s5_008"
down_revision = "p7_s5_007"
branch_labels = None
depends_on = None

_FK_NAME = "fk_projects_workspace_id"
_TABLE = "projects"


def upgrade() -> None:
    """补上这条外键（先 drop(if_exists) 再 create，天然幂等）."""
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey", if_exists=True)
    op.create_foreign_key(
        _FK_NAME, _TABLE, "workspaces", ["workspace_id"], ["workspace_id"]
    )


def downgrade() -> None:
    """删掉这条外键，回到「ORM 声明了但 DB 没有」的原始状态."""
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey", if_exists=True)
