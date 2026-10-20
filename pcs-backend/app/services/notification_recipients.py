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
    project_id: uuid.UUID,
    exclude_user_ids: tuple[uuid.UUID, ...] = (),
) -> list[uuid.UUID]:
    """持有**全局角色** `role`、且**有该项目授权**的启用用户。

    ⚠️ `project_id` **必填**，不给默认值 —— 「不限项目范围地发通知」这个用法
    本版不存在，留一个可选参数等于留一个**忘了传就越权**的坑（bug-2030 的
    同类：缺了约束，调用点不会报错，只是不漏地少收或多收）。

    ## 为什么只看全局角色，不看 `role_in_project`

    签署矩阵的 `sign_role` 是**全局角色**：`DeliverableService.sign_step` 拿
    `actor.role`（token 的 role claim）与 `step["sign_role"]` 直接比较，不匹配
    就 403 `SIGN_STEP_ROLE_MISMATCH`。而项目那一侧（`_authorize` →
    `check_project_access_or_404`）只校验**成员身份**，不看角色。

    ⇒ 「能签第 N 步」的充要条件 = **有项目授权 且 全局角色 == step.sign_role**。

    所以本函数与 `compute_todos` 都必须按**全局角色**圈人：
    按 `role_in_project` 圈人会通知 / 列出那些**点了必然 403**的人 ——
    「待办里有，点进去说你不是」比没有待办更坏。

    ## 为什么给了 `project_id` 时候选集先受项目授权约束

    一个全局角色是 DESIGNER、但**没有该项目授权**的人，不得收到该项目的
    通知（通知体里带着交付物标题与 project_id，那是不该让他看到的东西），
    也点不开那个待办。

    这条约束是**对齐待办侧**的：`compute_todos` 按 `user_projects` 圈人，
    通知侧若不圈，两边就漂移了 —— 症状是「待办里没有他，通知里有他」，
    而两边各自都「正常」。
    """
    recipients: dict[uuid.UUID, None] = {}

    # ⚠️ 候选集 = 本项目**有有效授权**的人。授权之外的人一律不收。
    candidates = await db.execute(
        select(UserProject.user_id).where(
            UserProject.project_id == project_id,
            UserProject.revoked_at.is_(None),
        )
    )
    candidate_ids = {uid for (uid,) in candidates.all()}

    # 全局角色。ACTIVE 过滤在 SQL 里 —— 离职的人不该再收通知。
    active = await db.execute(
        select(User.user_id, User.roles).where(User.status == "ACTIVE")
    )
    for uid, roles in active.all():
        if uid not in candidate_ids:
            continue
        if isinstance(roles, list) and role in roles:
            recipients[uid] = None

    for uid in exclude_user_ids:
        recipients.pop(uid, None)
    return list(recipients)
