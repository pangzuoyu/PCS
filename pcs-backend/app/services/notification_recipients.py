"""角色 → 收件人解析（通知接线 C1b 与待办实时计算 C4 的**共用** helper）。

## 为什么是共用而不是各写一份

签署矩阵的 `sign_role` 是**角色名**，不是用户。把它变成「哪些人该收到」需要
一条规则，而这条规则**有两处消费方**：通知触发（写）与待办实时计算（读）。
两份规则必然漂移，漂移的症状很安静 —— 通知发给了 A，待办列给 B，两边都「正常」。

⇒ 单一来源是本模块。

## 角色取「全局 ∪ 项目内」

`users.roles`（全局 JSONB）与 `user_projects.role_in_project`（项目内）**两者都算**。
只取全局的话，被只在某个项目里授予复核权的人永远收不到通知、也永远没有待办 ——
而 `user_projects` 才是 BLOCKER-3 之后真正的授权事实来源。

已撤销的项目授权（`revoked_at` 非空）与已停用用户（`status != ACTIVE`）一律排除。

## ⚠️ 全局角色的查询是一次 users 表读

`users.roles` 是 JSONB，跨方言的包含判断需要把候选行读上来在 Python 里过滤
（SQLite 单测环境没有 PG 的 JSONB `@>`）。PCS 是团队级单实例系统，users 表
规模在几十~几百行，一次全表读对**低频用户动作**（签署/审批）完全可接受。

若将来 users 表涨到数千行：改成 PG 的 `roles @> '["X"]'::jsonb` + GIN 索引，
**并**加一条 SQLite 环境的 skip 守卫 —— 别让测试继续绿在一个 PG 上根本不
会跑的查询上。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import User, UserProject


async def resolve_role_recipients(
    db: AsyncSession,
    *,
    role: str,
    project_id: uuid.UUID | None = None,
    exclude_user_ids: tuple[uuid.UUID, ...] = (),
) -> list[uuid.UUID]:
    """持有 `role` 的启用用户。`project_id` 给定时额外计入项目内角色。"""
    recipients: dict[uuid.UUID, None] = {}

    if project_id is not None:
        rows = await db.execute(
            select(UserProject.user_id).where(
                UserProject.project_id == project_id,
                UserProject.role_in_project == role,
                UserProject.revoked_at.is_(None),
            )
        )
        for (uid,) in rows.all():
            recipients[uid] = None

    # 全局角色。ACTIVE 过滤在 SQL 里 —— 离职的人不该再收通知。
    active = await db.execute(
        select(User.user_id, User.roles).where(User.status == "ACTIVE")
    )
    for uid, roles in active.all():
        if isinstance(roles, list) and role in roles:
            recipients[uid] = None

    # 项目内授权可能落在已停用用户上 —— 全局过滤拿不到他们，这里剔除。
    if project_id is not None:
        disabled = await db.execute(
            select(User.user_id).where(User.status != "ACTIVE")
        )
        for (uid,) in disabled.all():
            recipients.pop(uid, None)

    for uid in exclude_user_ids:
        recipients.pop(uid, None)
    return list(recipients)
