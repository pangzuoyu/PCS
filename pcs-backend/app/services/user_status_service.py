"""用户**账号状态**判定（P9B-4 T0-B · TODO-132 · 评审 #10）。

## 为什么单独一个模块

「禁用用户能不能访问」是**账号有效性**判定，不是**项目授权**判定 ⇒
与 `user_project_service`（项目授权行）分开 ⇒ 两套口径不会互相污染。

## 判定语义

| `users` 表 | 判定 |
|---|---|
| **无该行的行** | **放行** |
| `status = DISABLED` | **拒**（401 `USER_DISABLED`） |
| `status = ACTIVE` | 放行 |

## ⚠️「判定只在一处」指的是**比较**，不是**查表**

**比较**（`status` 是不是 `DISABLED`）⇒ **全仓唯一实现**：
`is_disabled_status()`（本模块）⇒ 三个调用点都走它：

| 调用点 | **查表键** | 用途 |
|---|---|---|
| `is_account_disabled`（actor 层） | `users.user_id` | 每请求（停用立即生效） |
| `token_issuer.issue_tokens` | `users.username` | 登录时拦停用用户 |
| `ad_sync` | `users.username` | 离开 AD 的用户 ⇒ 停用 |

⚠️ **查表键不同是刻意的**：登录时**只有用户名**（token 里的 `user_id` 是
派生值，而遗留行的 `user_id` 可能不是派生值 ⇒ 按 `user_id` 查会查不到）。

⚠️ **但两条路径在遗留行上会给出相反结论**（**已知边界** · TODO-137）：
遗留行（`user_id` ≠ 派生值）若是 `DISABLED` ⇒
**登录被拒**（按 username 查得到），而**在手 token 仍可用**
（actor 层按派生 `user_id` 查 ⇒ 无行 ⇒ 按下表「无行 ⇒ 放行」放行）。
⇒ 暴露面很小（遗留行的 id 对不上 ⇒ 物流面**处处 404** · TODO-137），
但这条边界**是真的** ⇒ 本 docstring 明写，不再假装「只有一处」。

## ⚠️「无行 ⇒ 放行」是**必须的**（不是宽松，是正确）

① **mock 登录不落 `users` 表**（ADR-0046 §③b：mock 与真实 AD 同名 ⇒
   落同一行 ⇒ 权限污染**且不报错**）⇒ 判成拒 ⇒ **dev / E2E 的 mock 登录全线挂掉**；
② **遗留账号行**（`user_id` ≠ 派生值 · TODO-137）⇒ token 里的 `user_id`
   查不到行 ⇒ 判成拒 ⇒ 遗留用户**全部**被锁在门外（比现在更糟）。

⇒ 「查不到行」只说明「这个身份没有账号元数据」⇒ **不能据此判它被停用**。

## 为什么是**每请求**查（而不是只在登录时查）

真实登录路径在**发 token 时**拦禁用用户（`token_issuer` ⇒ 401
`USER_LOGIN_DENIED_DISABLED`）⇒ 但**已经发出的 access token 仍然有效**
⇒ 「停用」形同虚设（禁用用户带着在手 token 仍能访问 20+ 物流端点）。

⇒ 每请求在 **actor 层**查一次 ⇒ 停用**立即生效**。
⚠️ 代价是**每请求多一次查询**（实测数字见 P9B-4 的 ledger + commit 正文）⇒
若 P95 超标，唯一出路是「把 `status` 塞进 token claim」（**破坏性变更**，
token 结构 + 所有签发路径 + 所有验证路径 ⇒ 独立批，不在本批顺手做）。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserStatus
from app.models.project import User


def is_disabled_status(status: str | None) -> bool:
    """这个 `status` 是不是「**被停用**」。

    ⚠️ **全仓唯一的比较实现**（P9B-4 评审 #10）⇒ 改 `status` 词表**只改这一处**
    ⇒ 三个调用点（每请求 / 登录 / AD 同步）都走它。
    ⚠️ **比较**（`== DISABLED`）与**查表**（按 `user_id` 还是 `username`）是**两件事**
    ⇒ 本函数只管前者（查表键见模块 docstring）。
    """
    return status == UserStatus.DISABLED.value


async def is_account_disabled(session: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """该账号是否被停用（`users.status == DISABLED`）。

    ⚠️ **无行 ⇒ False（放行）** —— 理由见模块 docstring（mock 登录 / 遗留行）。
    """
    status = (
        await session.execute(
            select(User.status).where(User.user_id == user_id)
        )
    ).scalar_one_or_none()
    return is_disabled_status(status)
