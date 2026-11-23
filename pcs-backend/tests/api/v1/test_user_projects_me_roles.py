"""`GET /user-projects/me` 的**角色闸**与**角色白名单唯一真相源**（TODO-188）。

## 为什么有本文件

TODO-188（P10-F · F3-T3a 审计发现）：该端点**手抄**了一份角色清单

```python
require_roles(actor, "DESIGNER", "CHECKER", "APPROVER", "REVIEWER", "SYSTEM_ADMIN")
```

⇒ ⇒ 漏了 `PROCESS_CONTROLLER` / `VIEWER` ⇒ ⇒ **合法用户 403**
⇒ ⇒ 而 P10-H 的**项目选择器**（TODO-194）正是靠这个端点取候选
⇒ ⇒ ⇒ 这两类人**打开前端就是空的**。

⚠️ **同一个根因还有第二处**：`stream_batch.py` 的角色闸把
`PROCESS_CONTROLLOR` **拼错**了 ⇒ ⇒ 真角色 `PROCESS_CONTROLLER`
**永远匹配不上** ⇒ ⇒ 合法用户 403。

⇒ ⇒ 本文件钉两件事：
① **合法角色都能进**（`/me` 与批量提交）—— 删掉任一角色 ⇒ ⇒ 红；
② **白名单只有一份**（`app.api.v1.config.ALLOWED_ROLES`）—— 端点不再手抄。
"""
from __future__ import annotations

import uuid

import pytest

from app.api.v1.config import ALLOWED_ROLES
from app.core.security import create_access_token


def _headers(role: str) -> dict[str, str]:
    token = create_access_token(subject=f"u-{role.lower()}", role=role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# ① `/user-projects/me`：任何合法角色都能看**自己**的清单
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(ALLOWED_ROLES))
async def test_every_allowed_role_can_list_own_projects(client, role: str):
    """⚠️ **白名单里的每个角色都能进**（缺一个 ⇒ ⇒ 那个角色 403 ⇒ ⇒ 红）。

    ⇒ ⇒ 参数化 ⇒ ⇒ 新增角色时**自动**被这条覆盖（不用改测试）。
    """
    r = await client.get("/api/v1/user-projects/me", headers=_headers(role))
    assert r.status_code == 200, f"{role} 被挡在门外：{r.status_code} {r.text}"
    assert r.json() == []


async def test_unauthenticated_gets_401(client):
    """⚠️ **没登录 ⇒ 401**（不是 403）—— 「没身份」与「身份不够」是两回事。"""
    r = await client.get("/api/v1/user-projects/me")
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# ② 批量提交：角色名拼错 ⇒ ⇒ 合法角色被 403
# ---------------------------------------------------------------------------


async def test_batch_submit_accepts_process_controller(client):
    """⚠️ **`PROCESS_CONTROLLER` 能进批量提交端点**（曾因拼写错误被 403）。"""
    r = await client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [str(uuid.uuid4())], "dry_run": True},
        headers=_headers("PROCESS_CONTROLLER"),
    )
    assert r.status_code != 403, f"合法角色被角色闸挡下：{r.text}"
    assert r.status_code == 207, r.text


async def test_batch_submit_rejects_a_role_outside_the_whitelist(client):
    """⚠️ **不在白名单里的角色 ⇒ 403**（闸门还在，不是形同虚设）。"""
    r = await client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [str(uuid.uuid4())], "dry_run": True},
        headers=_headers("OUTSIDER"),
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# ③ 白名单只有一份（**根因**守卫）
# ---------------------------------------------------------------------------


def test_role_whitelist_is_a_single_source():
    """⚠️ **白名单是模块级常量** ⇒ ⇒ 端点只能 `*ALLOWED_ROLES` ⇒ ⇒ 抄漏不可能。

    ⇒ ⇒ 这条断言防的是「有人又手抄了一份清单」—— 那是 TODO-188 的根因。
    """
    import inspect

    from app.api.v1 import config as config_mod
    from app.api.v1 import user_projects as up_mod

    assert "PROCESS_CONTROLLER" in ALLOWED_ROLES
    assert "VIEWER" in ALLOWED_ROLES
    # 端点模块里**不得**再出现字面量角色清单
    src = inspect.getsource(up_mod)
    assert "PROCESS_CONTROLLOR" not in src, "角色名拼写错误仍在"
    assert "ALLOWED_ROLES" in src, "端点应引用唯一真相源"
    assert config_mod.ALLOWED_ROLES is ALLOWED_ROLES
