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
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import UserProject

VALID_PROJECT_ROLES = {"DESIGNER", "CHECKER", "APPROVER", "REVIEWER", "VIEWER"}


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
            role_in_project: 项目内角色 (DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER)
            granted_by: 授权人 user_id (None = SYSTEM 角色授权)

        Returns:
            UserProject 记录 (新建或更新)

        Raises:
            ValueError: role_in_project 不在合法 5 角色内
        """
        if role_in_project not in VALID_PROJECT_ROLES:
            raise ValueError(
                f"role_in_project {role_in_project!r} 不在合法 5 角色: "
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
        session.add(record)
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
