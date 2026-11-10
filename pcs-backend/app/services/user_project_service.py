"""UserProjectService — 用户-项目关联管理 + 访问守卫 (P7-7+ BLOCKER-3 修复)。

业务：
- grant_project_access: 管理员授予用户项目访问权（含角色）
- revoke_project_access: 撤销（保留历史，revoked_at 非空）
- _check_user_project_access: API 守卫函数 (每 endpoint 调用)
- list_user_projects: 用户可见项目列表

全局角色与项目内角色区分：
- 全局 roles: 用户系统级能力 (DESIGNER/SYSTEM_ADMIN/...) — 决定可调哪些 API 类别
- 项目内 role_in_project: 用户在该项目内的角色 — 决定可调哪些项目数据
例: 全局 DESIGNER 可调 equipment-list API; 但仅当其 user_projects 含
project_id 行时才能访问该项目数据。

BLOCKER-3 修复: 替换原 "信任 client project_id" → 现 "信任 token user_id +
UserProject ACL 校验"。
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import UserStatus
from app.models.project import User, UserProject

#: 项目内角色词表。
#:
#: ⚠️ `PROJECT_LEAD`（项目负责人）是 **2026-10-26 用户裁决**新增的：
#: 「**只有项目负责人能绑签署矩阵**」⇒ 绑定/解绑端点按**项目内角色**判
#: （见 `app/api/v1/signature_matrices.py::_BIND_PROJECT_ROLES`）。
#: 词表来源：`spec/校审层级可配置化增补规格说明书.md` §2.1.2「项目负责人（新增）——
#: 可指定为任意签署角色（项目级临时指派）」。
#:
#: ⚠️ 词表**无序**（平行职责，不是等级）⇒ 不按它分级。
VALID_PROJECT_ROLES = {
    "DESIGNER",
    "CHECKER",
    "APPROVER",
    "REVIEWER",
    "VIEWER",
    "PROJECT_LEAD",
}


class UserProjectService:
    """用户-项目关联 service（user_projects 表）。"""

    @classmethod
    async def grant_project_access(
        cls,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        role_in_project: str,
        granted_by: uuid.UUID | None = None,
    ) -> UserProject:
        """授予用户项目访问权（同 user_id+project_id 已存在则覆盖角色）。

        Args:
            session: AsyncSession
            user_id: 目标用户 UUID
            project_id: 目标项目 UUID
            role_in_project: 项目内角色 (DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER/PROJECT_LEAD)
            granted_by: 授权人 user_id (None = SYSTEM 角色授权)

        Returns:
            UserProject 记录 (新建或更新)

        Raises:
            ValueError: role_in_project 不在合法 6 角色内
        """
        if role_in_project not in VALID_PROJECT_ROLES:
            raise ValueError(
                f"role_in_project {role_in_project!r} 不在合法 6 角色: "
                f"{sorted(VALID_PROJECT_ROLES)}"
            )

        # 查现存行 (含已撤销)
        stmt = select(UserProject).where(
            UserProject.user_id == user_id,
            UserProject.project_id == project_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.role_in_project = role_in_project
            existing.granted_by = granted_by
            existing.revoked_at = None
            existing.revoked_by = None
            await session.commit()
            await session.refresh(existing)
            return existing

        record = UserProject(
            user_id=user_id,
            project_id=project_id,
            role_in_project=role_in_project,
            granted_by=granted_by,
        )
        try:
            # ⚠️ `session.add` 必须在 savepoint **之内**（`begin_nested()` 会先
            #    flush pending ⇒ savepoint 之外的 INSERT 撞约束时会**中止整个
            #    事务** —— 调用方（POST /projects）的项目 INSERT 与本插入同
            #    事务 ⇒ 整体回滚）。
            #    配方来源：`docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`
            #    （同文件里已修好的同族方法 `_get_or_create_default_record_matrix`）。
            async with session.begin_nested():
                session.add(record)
                await session.flush()
        except IntegrityError:
            # ⚠️ 并发插同一 `(user_id, project_id)` ⇒ **重读赢家**。
            #    ⚠️ **只读不写**：绝不把赢家的列改回自己的版本（那是第二种数据损坏）。
            winner = (await session.execute(stmt)).scalar_one_or_none()
            if winner is None:
                raise  # 不是那唯一约束 ⇒ 原样抛
            await session.commit()
            await session.refresh(winner)
            return winner
        await session.commit()
        await session.refresh(record)
        return record

    @classmethod
    async def revoke_project_access(
        cls,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        revoked_by: uuid.UUID,
    ) -> UserProject | None:
        """撤销用户项目访问权（保留历史，revoked_at 非空）。

        Returns:
            更新后的 UserProject 记录；None 如果原本无访问权。
        """
        stmt = select(UserProject).where(
            UserProject.user_id == user_id,
            UserProject.project_id == project_id,
            UserProject.revoked_at.is_(None),
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return None
        record.revoked_at = _now()
        record.revoked_by = revoked_by
        await session.commit()
        await session.refresh(record)
        return record

    @classmethod
    async def check_user_project_access(
        cls,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        required_role: str | None = None,
    ) -> bool:
        """守卫: 校验 user_id 对 project_id 是否有有效访问权。

        Args:
            session: AsyncSession
            user_id: 当前 actor user_id (从 token)
            project_id: 客户端传入的 project_id
            required_role: 必需的项目内角色 (None = 任意角色即可)

        Returns:
            True = 有权访问；False = 无权

        注: 全局 SYSTEM_ADMIN 角色默认可访问所有项目（由 _check_user_project_access
        在 API 层做 bypass 配合）。本函数仅做 UserProject 行检查。
        """
        stmt = select(UserProject).where(
            UserProject.user_id == user_id,
            UserProject.project_id == project_id,
            UserProject.revoked_at.is_(None),
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        if record is None:
            return False
        if required_role is not None:
            return record.role_in_project == required_role
        return True

    @classmethod
    async def list_user_projects(
        cls,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        include_revoked: bool = False,
    ) -> Sequence[UserProject]:
        """列出用户有效 (默认) / 全部 (含 revoked) 项目。"""
        stmt = select(UserProject).where(UserProject.user_id == user_id)
        if not include_revoked:
            stmt = stmt.where(UserProject.revoked_at.is_(None))
        result = (await session.execute(stmt)).scalars().all()
        return result


def _now() -> "datetime.datetime":  # type: ignore[name-defined]
    """轻量 helper 避免循环 import。"""
    import datetime as dt

    return dt.datetime.now(dt.UTC)


async def has_project_access(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_roles: list[str] | None = None,
) -> bool:
    """项目访问权判定（**含 SYSTEM_ADMIN bypass**）—— 只回 bool，**不抛异常**。

    ## 为什么要有它（而不是直接用 `check_project_access_or_404`）

    `app/api/v1/_guard.py::check_project_access_or_404` 无权时抛
    `HTTPException(404, "Project not found: <id>")` ⇒ 全局 handler 把它渲染成
    信封 **`code="HTTP_404"` / `message="Project not found: …"`**；
    而「物流不存在」走 `PcsError(SIM_STREAM_NOT_FOUND)` ⇒ 信封
    **`code="SIM_STREAM_NOT_FOUND"` / `message="Stream … 不存在"`**。

    ⇒ **两个 404 的信封完全不同** ⇒ 攻击者能靠 `code`/message 区分
    「这个 UUID 不存在」与「这个 UUID 存在但不属于我」⇒ **可枚举 UUID**。

    ⇒ 所以本函数只做**判定**，由调用方决定**抛什么** ⇒ 调用方可以抛**与
    「不存在」逐字相同**的 `PcsError` ⇒ 无权 ≡ 不存在。

    ## 口径与 `check_project_access_or_404` **完全一致**

    SYSTEM_ADMIN 全局 bypass + 同样的 `UserProject` 行判定 ⇒ 两处不会漂移。

    ⚠️ 放 **service 层** ⇒ `app/services/` **不**反向 import `app/api/v1/`。
    """
    if actor_roles and "SYSTEM_ADMIN" in actor_roles:
        return True
    return await UserProjectService.check_user_project_access(
        session, user_id=user_id, project_id=project_id
    )


async def ensure_user_row(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    username: str,
) -> User:
    """确保 `users` 表里有该用户的行（**有则原样返回，绝不改任何字段**）。

    ## 为什么需要它

    `user_projects.user_id` 是 **NOT NULL 的 FK → `users.user_id`**，而
    PostgreSQL **强制**它 —— SQLite 单测**默认不强制** ⇒ 缺 `users` 行的测试
    会**本地绿、生产炸**（这正是本仓最熟悉的「漂移盲区」形状）。
    ⇒ 任何要写 `user_projects` 的路径，都得先保证用户行存在。

    ## 为什么**建行时 `roles` 写空数组**

    - 请求路径的 ACL 权威是 **JWT 的 role claim**
      （`app/api/v1/config.py::current_actor` → `require_roles`），
      **不是** `users.roles` ⇒ 空 roles 不影响鉴权。
    - ADR-0046 §③b 禁止 **mock 登录**往 `users.roles` 写角色（mock 与真实 AD
      同名 ⇒ 污染同一行 ⇒ 权限污染**且不报错**）⇒ 这里**只建行、不写角色**。

    ## 为什么**已有行绝不改**

    真实登录路径（`app/services/token_issuer.py::issue_tokens`）已经**惰性建行**
    并写入真实 roles ⇒ 本函数的职责只是「保证行存在」⇒ 改 roles 会覆盖真实身份。

    ## 查找顺序（**只认 `user_id`** —— 不按 username 兜底）

    ⚠️ **绝不按 `username` 兜底**（ce-code-review P2 #10 · bug-2150）：

    原来这里是「先按 `user_id` 找 ⇒ 再按 `username` 找 ⇒ 都没有才新建」，
    而**username 兜底返回的那行可能 `user_id` 与请求方完全不同** ⇒
    调用方（`POST /projects`）随后按 `creator.user_id` 授权 ⇒
    **授权落在一个「请求方的 token 根本不认」的身份上** ⇒
    - 创建者**访问不到自己刚建的项目**（处处 404）；
    - 而**另一个账号**被授了权。

    ⇒ 现在：**只认 `user_id`** ⇒ 返回的行**必然**就是请求方那个身份。
    ⇒ username 已被**别人**占着（遗留行）⇒ 撞唯一约束 ⇒ **显式报错**
    （不静默替换）⇒ 运维按 TODO 里的迁移步骤把遗留授权 transfer 到派生 id。

    ## ⚠️ 遗留行的迁移（一次性运维动作，不是代码逻辑）

    `users.username` 唯一 ⇒ 派生 id 与遗留 id **不能并存** ⇒ 迁移顺序：
    ① 把遗留行的 username 改成不冲突的值（如 `legacy:<原名>`）→
    ② 建派生 id 的行（username 用原名）→
    ③ `UPDATE user_projects SET user_id = <派生 id> WHERE user_id = <遗留 id>`。
    """
    row = await session.get(User, user_id)
    if row is not None:
        return row

    row = User(
        user_id=user_id,
        username=username,
        display_name=username,
        roles=[],
        ad_groups=[],
        status=UserStatus.ACTIVE.value,
    )
    try:
        # ⚠️ `session.add` 必须在 savepoint **之内**（`begin_nested()` 会先
        #    flush pending ⇒ savepoint 之外的 INSERT 撞 `users.username` 唯一
        #    约束时会**中止整个事务** —— 调用方（POST /projects）的项目 INSERT
        #    与本插入同事务 ⇒ 整体回滚）。
        #    配方来源：`docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        # ⚠️ 并发首建撞车（两个请求都「库为空 + 都要建」）⇒ **重读赢家**。
        #    ⚠️ **只读不写**：绝不改赢家的列（那会把赢家的身份改回自己的版本）。
        winner = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if winner is None:
            raise  # 不是 username 唯一约束 ⇒ 原样抛
        if winner.user_id != user_id:
            # ⚠️⚠️ **username 已被别人占着**（遗留行）⇒ **显式报错**，
            #    绝不静默返回一个「不是请求方」的身份（bug-2150）。
            raise PcsError(
                code="USER_ID_CONFLICT",
                message=(
                    f"用户名 {username!r} 已存在一条 user_id 不同的遗留账号行"
                    f"（{winner.user_id}）⇒ 本次请求的身份是 {user_id} ⇒ "
                    "无法安全授权（授权会落到请求方不认的身份上）⇒ "
                    "请先按迁移步骤把遗留账号的授权转到派生 id"
                ),
                status=409,
            )
        return winner
    return row
