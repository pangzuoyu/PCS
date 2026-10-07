"""p7_s5_007: 补 user_projects 的 4 个外键 —— 建表迁移把它们静默丢弃了（bug-144）.

## 根因

`p7_open_010_user_projects_blocker3.py:40-43` 把裸 `sa.ForeignKey(...)` 当作**位置参数**
传给 `op.create_table`：

    op.create_table(
        "user_projects",
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        ...
        sa.ForeignKey("users.user_id", ondelete="CASCADE",
                      name="fk_user_projects_user_id"),
        sa.ForeignKey("projects.project_id", ondelete="CASCADE",
                      name="fk_user_projects_project_id"),
        sa.ForeignKey("users.user_id", name="fk_user_projects_granted_by"),
        sa.ForeignKey("users.user_id", name="fk_user_projects_revoked_by"),
    )

`op.create_table(*args)` 只接受 `Column` / `Constraint`。裸 `ForeignKey` 两者都不是，
**被无声吞掉 —— 不报错、不告警**。正确写法是嵌进列定义：

    sa.Column("user_id", UUID(as_uuid=True),
              sa.ForeignKey("users.user_id", ondelete="CASCADE",
                            name="fk_user_projects_user_id"),
              nullable=False)

ORM 侧（`app/models/project.py:184-211`）用的是 `mapped_column(ForeignKey(...))`，
元数据里确实有 4 条约束 —— 错的只有迁移。

真库证据：`pg_constraint` 查 `user_projects` 共 8 条约束，全是 PK / UNIQUE / NOT NULL，
**FK 一条都没有**；SQLAlchemy inspector 反射同样返回 `[]`。

## 影响

`user_projects` 是 **BLOCKER-3 IDOR 守卫**（`_check_user_project_access`）读的那张表。
没有 FK 意味着：

- 授权可以指向不存在的 `user_id` / `project_id`，留下永久孤儿行
- `ondelete="CASCADE"` 从不发生 —— 删除用户/项目后残留授权继续生效
- 而 login 用的 `user_id = uuid5(NAMESPACE_DNS, username)` 是**确定性派生**的，
  同名用户名重建后拿到同一个 id，**旧授权会被无声继承**

## 约束名对齐 ORM

ORM 侧实际名字（SQLAlchemy 按 naming_convention 生成，**不是**建表迁移里写的那些）：
`fk_user_projects_user_id_users` / `fk_user_projects_project_id_projects` /
`fk_user_projects_granted_by_users` / `fk_user_projects_revoked_by_users`。
用 ORM 的名字，否则 `alembic check` 仍会报漂移（名字对不上也算漂移）。

## ⚠️ 孤儿数据核查

应用前查过 pcs 库：`user_projects` **0 行**，`users` / `projects` 亦 **0 行**，
故无孤儿行阻挡 ADD CONSTRAINT。若某环境已有数据，需先清理孤儿，否则 PG 会拒绝。

⚠️ 注意 users / projects 目前也是空表 —— `users` 要等 P9 的 AD 同步
（`P9-ADM-001`）才会有行。FK 指向空表本身合法（约束只在有行插入时才生效），
但**在 users 有数据之前，grant_project_access 仍会因 FK 而失败**。这是 P9 未开工
的现状，不是本迁移的问题。

Revision ID: p7_s5_007
Revises: p7_s5_006
Create Date: 2026-10-07
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s5_007"
down_revision = "p7_s5_006"
branch_labels = None
depends_on = None

_TABLE = "user_projects"

# (约束名, 本表列, 被引用表, 被引用列, ondelete)
_FOREIGN_KEYS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("fk_user_projects_user_id_users", "user_id", "users", "user_id", "CASCADE"),
    ("fk_user_projects_project_id_projects", "project_id", "projects", "project_id", "CASCADE"),
    ("fk_user_projects_granted_by_users", "granted_by", "users", "user_id", None),
    ("fk_user_projects_revoked_by_users", "revoked_by", "users", "user_id", None),
)


def upgrade() -> None:
    """补 4 条外键（每条先 drop_constraint(if_exists) 再 create，天然幂等）.

    ⚠️ **不能用裸 SQL 的 `REFERENCES users.user_id` 写法**。实测 PG 报
    `InvalidSchemaName: schema "users" does not exist` —— 该形式对 `users` 这个
    标识符不成立，连临时表上复现也一样，而 `REFERENCES users(user_id)`（函数式）
    与 `REFERENCES "users" ("user_id")`（加引号式）都正常。
    `op.create_foreign_key` 走正规 API，标识符引用由 alembic 处理，避开这个坑。
    """
    for name, column, ref_table, ref_column, ondelete in _FOREIGN_KEYS:
        op.drop_constraint(name, _TABLE, type_="foreignkey", if_exists=True)
        kwargs = {"ondelete": ondelete} if ondelete else {}
        op.create_foreign_key(
            name, _TABLE, ref_table, [column], [ref_column], **kwargs
        )


def downgrade() -> None:
    """删 4 条外键（IF EXISTS 幂等）."""
    for name, *_ in _FOREIGN_KEYS:
        op.drop_constraint(name, _TABLE, type_="foreignkey", if_exists=True)