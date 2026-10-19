"""ADMIN 用户管理端点（SPEC P9A-ADM-001/002，ADR-0046 §⑤）。

⚠️ **全环境挂载**，与 `mock_auth` 的形态**相反**：
`mock_auth` 是「生产不该有」（只在非生产 include），本 router 是「生产必须有」
—— 只在非生产挂载 ⇒ 生产上永远无法停用任何人 ⇒ `P9A-USR-004`
（离职处理：离职者在手令牌立即失效）根本无法验收。
鉴权靠 `require_roles("SYSTEM_ADMIN")`，不是靠「不挂载」。

**mock 用户不豁免**：停用 mock 用户在 QA 里没有意义且会误伤测试，
需要时在测试里 mock 掉，不要在这里开口子。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.services.ad_sync import sync_users
from app.services.admin_user_service import disable_user, list_users

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

#: 只有系统管理员能碰用户表。写死在这里而不是散在端点里 ——
#: 漏一处 `require_roles` 就是一条越权路径。
_ADMIN_ROLES = ("SYSTEM_ADMIN",)


class AdminUserOut(BaseModel):
    """用户列表条目（P9A-ADM-001）。

    业务：显式声明全部字段（零裸字段约束 P9A-DLV-010）——
    禁止 `response_model=dict`，那会让契约随 ORM 漂移。
    `token_version` 对外可见：它是「已吊销了几轮」的运营视角。
    """

    user_id: uuid.UUID
    username: str
    display_name: str
    email: str | None
    department: str | None
    roles: list[str]
    status: str
    token_version: int
    last_login_at: datetime | None


class UserDisabledOut(BaseModel):
    """停用结果（P9A-ADM-002）。回显新的 `token_version` 便于前端确认。"""

    user_id: uuid.UUID
    username: str
    status: str
    token_version: int


class AdSyncResultOut(BaseModel):
    """AD 同步结果（P9A-USR-002 手动触发）。

    `ok=False` 表示**什么都没做**（目录连不上），不是「做了但有部分失败」。
    `skipped_empty=True` 表示枚举到 0 个用户，疑似 filter/base_dn 配错 ——
    此时同样不做任何写入，包括不做离职判定。

    `unmapped` 是「组未映射到角色」的计数。这些用户**不会被授予任何角色**
    （生产 fail-closed），已有角色也保持不动 —— 需要看这个数，运维才知道
    有人拿不到权限。
    """

    ok: bool
    created: int
    updated: int
    departed: int
    unmapped: int
    skipped_empty: bool
    error: str | None


@router.get("", response_model=list[AdminUserOut])
async def get_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> list[AdminUserOut]:
    """GET /admin/users：用户列表（供演示 disable 前后的状态对比）。"""
    require_roles(actor, *_ADMIN_ROLES)
    return [AdminUserOut(**u) for u in await list_users(db)]


@router.put("/{user_id}/disable", response_model=UserDisabledOut)
async def put_disable_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> UserDisabledOut:
    """PUT /admin/users/{id}/disable：停用用户。

    同事务做三件事（ADR-0046 §⑤）：
    1. `status = DISABLED` —— 挡住后续登录
    2. `token_version += 1` —— **已签发的 refresh 全部失效**（跨进程有效）
    3. 写 `USER_DISABLED` 审计（谁停的）

    ⚠️ 已知边界（不得表述为已解决）：`access` token 不带 `tv`，
    在手 access 仍可用至过期（默认 30 分钟）。见 ADR-0046 §⑤。
    """
    require_roles(actor, *_ADMIN_ROLES)
    return await disable_user(
        db, user_id=user_id, actor_user_id=actor.user_id, actor_username=actor.username,
    )


@router.post("/sync", response_model=AdSyncResultOut)
async def post_sync_ad_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> AdSyncResultOut:
    """POST /admin/users/sync：手动触发一次全量 AD 同步（P9A-USR-002）。

    未配置服务账号时返 **503 `LDAP_SYNC_NOT_CONFIGURED`** ——
    返 200 空结果会让运维以为「同步过了、没有变化」，那是更坏的失败。
    """
    require_roles(actor, *_ADMIN_ROLES)
    return AdSyncResultOut(**(await sync_users(db)).as_dict())
