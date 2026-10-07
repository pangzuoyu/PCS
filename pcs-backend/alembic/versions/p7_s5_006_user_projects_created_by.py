"""p7_s5_006: 补 user_projects.created_by —— ORM 继承来的列，真库缺失，导致授权必失败.

发现路径: 2026-10-07 应用 `p7_s5_005` 后 `alembic check` 首次能跑，350 条漂移里
唯一的非注释项 —— `add_column user_projects.created_by`。

## 根因

`UserProject` 继承 `TimestampMixin`（`app/models/mixins.py:35`），mixin 声明
`created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)`，故 ORM 期望该列存在。
但建表迁移 `p7_open_010_user_projects_blocker3` 是**手写**的 `op.create_table`，
逐列抄写时只抄了 `created_at` / `updated_at`，漏了 `created_by`。

`p6_5_006_orm_db_drift_final_fix` 曾批量补过全库缺失的 mixin 列，但 `user_projects`
比它晚建（属 P7-7+ BLOCKER-3），不在那次补列范围内，于是漏网。

## 影响：授权功能在真库上整体不可用（非「列可为 NULL 所以没事」）

SQLAlchemy 的 ORM INSERT 会把无默认值的可空列也写进列清单：

    INSERT INTO user_projects (id, user_id, project_id, role_in_project,
                               granted_at, created_by, created_at, updated_at)
    VALUES (...)

真库实测（已回滚，无数据变更）：

    psycopg.errors.UndefinedColumn: column "created_by" of relation
    "user_projects" does not exist

`UserProjectService.grant_project_access`（`app/services/user_project_service.py:81`）
正是这条 INSERT —— 而它写的是 **BLOCKER-3 IDOR 守卫**要读的授权表。授权写不进去，
`_check_user_project_access` 无数据可读。

**为什么全量 3954 条单测照绿**：单测跑内存 SQLite，schema 由
`SA_Base.metadata.create_all` 从 ORM 生成，列自然存在。只有真 Postgres 才暴露 ——
正是 CLAUDE.md「漂移盲区」警告的情形：缺表会红，漂移会绿。

UPDATE 路径不受影响（ORM 只 SET 脏字段），故本条只炸新增授权。

## 列定义

对齐 `TimestampMixin.created_by` 与全库其余 50 张表：裸 `uuid`、可空、无 FK、无
server_default、无 comment（mixin 未声明 comment，故不产生 modify_comment 漂移）。

⚠️ 存量数据：`user_projects` 若已有行，本迁移只加列不赋默认值，取值仍为 NULL，
与「匿名操作可空」的 mixin 语义一致，无需回填。

Revision ID: p7_s5_006
Revises: p7_s5_005
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_006"
down_revision = "p7_s5_005"
branch_labels = None
depends_on = None

_TABLE = "user_projects"


def upgrade() -> None:
    """补 created_by 列（PG 原生 IF NOT EXISTS，天然幂等）."""
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS created_by UUID")


def downgrade() -> None:
    """删列（IF EXISTS 幂等）."""
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS created_by")