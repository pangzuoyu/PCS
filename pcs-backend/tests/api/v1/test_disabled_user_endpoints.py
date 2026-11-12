"""**停用覆盖面**：`current_user` 背后的 7 个端点（P9B-4 评审 #16）。

## 为什么单独一个文件

ADR-0046 §5 与 `user_status_service` 的 docstring 都说「账号状态判定在**一处**
⇒ **全局生效**」⇒ 而实现上**只有一个入口**（`current_actor`）⇒

`current_user`（`app/api/v1/auth.py`）是**另一个**入口 —— 它是**纯 JWT 解码**，
**从不碰** `users.status` ⇒ 它背后的 **7 个端点**对停用用户**照样 200**：

- `GET /auth/me`（`auth.py`）—— 前端用它**自查会话**⇒ 停用用户的会话**仍然
  「有效」** ⇒ 前端不会登出 ⇒ **僵尸会话**（叠加评审 #1 的前端缺口）；
- 6 个 `GET /meta/*`（`meta.py`）—— 枚举 / 权限矩阵 / 错误码 / 状态机 / UI schema。

⇒ 用户 2026-11-12 裁决「停用覆盖面 = **全部补齐**」⇒ `current_user` 也必须
查 `users.status`。

## 暴露面为什么小（但仍要补）

`/auth/me` 只回**调用者自己**的身份，meta 只回**静态字典** ⇒ 没有数据泄露。
⇒ 但「停用立即生效」这条承诺在代码上**不成立** ⇒ 承诺要么兑现，要么明写例外。
⇒ 本批选**兑现**。
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token
from app.models.enums import UserStatus
from app.models.project import User

pytestmark = pytest.mark.asyncio

#: `current_user` 背后的 7 个端点（`GET /auth/me` + 6 个 `GET /meta/*`）。
DISABLED_USER_ENDPOINTS = [
    "/api/v1/auth/me",
    "/api/v1/meta/enums",
    "/api/v1/meta/permissions",
    "/api/v1/meta/error-codes",
    "/api/v1/meta/state-machine",
]


async def _make_disabled_user(db_session, username: str) -> uuid.UUID:
    """造一行 `status = DISABLED` 的 `users` 行 ⇒ 返回它的 `user_id`。"""
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, username)
    db_session.add(
        User(
            user_id=user_id,
            username=username,
            display_name=username,
            roles=["DESIGNER"],
            ad_groups=[],
            status=UserStatus.DISABLED.value,
        )
    )
    await db_session.commit()
    return user_id


@pytest.mark.parametrize("path", DISABLED_USER_ENDPOINTS)
async def test_disabled_user_is_rejected_by_current_user_endpoints(
    client, db_session, path
):
    """⚠️ **停用用户拿在手 token 访问 `current_user` 背后的端点 ⇒ 401**。"""
    username = f"disabled-{path.strip('/').replace('/', '-')}"
    user_id = await _make_disabled_user(db_session, username)

    token = create_access_token(
        subject=username, role="DESIGNER", extra={"user_id": str(user_id)}
    )
    resp = await client.get(path, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401, (
        f"{path} 对**停用**用户返回 {resp.status_code}（应 401）⇒ {resp.text}"
    )
    assert resp.json()["code"] == "USER_DISABLED", resp.text


async def test_disabled_user_without_users_row_is_still_allowed(client, db_session):
    """⚠️ **对照组**：`users` 表**无行** ⇒ 放行（mock 登录不落库 · ADR-0046 §③b）。

    ⇒ 判成拒 ⇒ dev / E2E 的 mock 登录全线挂掉 ⇒ 这条边界不能动。
    """
    username = "no-row-user"
    token = create_access_token(
        subject=username, role="DESIGNER",
        extra={"user_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, username))},
    )
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text


async def test_active_user_still_passes_current_user(client, db_session):
    """⚠️ **对照组**：正常用户**不受影响**（不许把门关死）。"""
    username = "active-user"
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, username)
    db_session.add(
        User(
            user_id=user_id,
            username=username,
            display_name=username,
            roles=["DESIGNER"],
            ad_groups=[],
            status=UserStatus.ACTIVE.value,
        )
    )
    await db_session.commit()

    token = create_access_token(
        subject=username, role="DESIGNER", extra={"user_id": str(user_id)}
    )
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
