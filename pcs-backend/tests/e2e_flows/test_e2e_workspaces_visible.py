"""种子工作区在切换器里**可见**（P10-F · F2-T2 · 评审 #24）。

## 为什么要有这个文件

⚠️ **前端永远带 `owner_id` 取工作区列表** ——
`DashboardPage` ⇒ `<WorkspaceSwitcher ownerId={userId}>` ⇒
`WorkspaceSwitcher` ⇒ `workspaceApi.list(ownerId)` ⇒
`src/api/sprint1.ts:16` ⇒ `params: ownerId ? { owner_id: ownerId } : {}`
⇒ ⇒ **不传 `owner_id` 就列出全部**（那是 admin 视图）⇒ ⇒ 前端永远**过滤**。

⇒ ⇒ 种子的工作区 `owner_id` 是 NULL ⇒ ⇒ **切换器里选不中** ⇒ ⇒
「补 `project_id`」那步**根本轮不到** ⇒ ⇒ 仪表盘那条路径在真后端下**没测过**。

⚠️ **要的是派生 id**（`derive_user_id`）—— `user_id` 是派生值 ⇒ 填用户名
⇒ ⇒ 列表按 `owner_id`（UUID）过滤 ⇒ ⇒ 过滤不到 ⇒ ⇒ 同一个病。
"""
from __future__ import annotations

import pytest

# ⚠️ **P10-F · F3（TODO-186）**：工作区列表**现在要登录**
# ⇒ ⇒ ⇒ 本文件原先**不带 `Authorization` 头** ⇒ ⇒ ⇒ 现在带 alice 的令牌
# ⇒ ⇒ ⇒ 且 `owner_id` 必须与**令牌里的那个人**一致（否则 403 —— admin 视图）。

from app.services.token_issuer import derive_user_id
from scripts.seed_e2e_flows import (
    FLOW_PERSONAL_WORKSPACE_ID,
    FLOW_PROJECT_ID,
    FLOW_WORKSPACE_ID,
)


@pytest.mark.e2e
async def test_seeded_workspaces_are_visible_to_their_owner(
    e2e_client, e2e_seed, role_headers
):
    """种子工作区必须**在切换器里可见** ⇒ `owner_id` 填**派生 id**。

    ⇒ ⇒ 断**后果**（「列表里有它」），不断**动作**（「我们调用了 seed」）。
    """
    resp = await e2e_client.get(
        f"/api/v1/workspaces?owner_id={derive_user_id('alice')}",
        headers=role_headers(username="alice"),
    )
    assert resp.status_code == 200, resp.text
    ids = {w["workspace_id"] for w in resp.json()}
    assert str(FLOW_WORKSPACE_ID) in ids, (
        f"种子 FORMAL 工作区不在 alice 的工作区列表里 ⇒ {ids}"
    )
    assert str(FLOW_PERSONAL_WORKSPACE_ID) in ids, (
        f"种子 PERSONAL 工作区不在 alice 的工作区列表里 ⇒ {ids}"
    )


@pytest.mark.e2e
async def test_formal_workspace_has_a_project_and_personal_has_none(
    e2e_client, e2e_seed, role_headers
):
    """FORMAL 工作区**有**项目（回填）· PERSONAL 工作区**没有**（按设计）。

    ⚠️ **两种形态都要有** —— 仪表盘的守卫条件是「**拿到了真 project_id**」
    ⇒ ⇒ 「无项目工作区」这个形态在真后端里**必须存在**，否则那条路径测不了。
    """
    resp = await e2e_client.get(
        f"/api/v1/workspaces?owner_id={derive_user_id('alice')}",
        headers=role_headers(username="alice"),
    )
    assert resp.status_code == 200, resp.text
    by_id = {w["workspace_id"]: w for w in resp.json()}

    formal = by_id[str(FLOW_WORKSPACE_ID)]
    assert formal["project_id"] == str(FLOW_PROJECT_ID), (
        f"FORMAL 工作区没有回填 project_id ⇒ {formal}"
    )

    personal = by_id[str(FLOW_PERSONAL_WORKSPACE_ID)]
    assert personal["workspace_type"] == "PERSONAL", personal
    assert personal["project_id"] is None, (
        f"PERSONAL 工作区**按设计**没有项目 ⇒ 不该有 project_id ⇒ {personal}"
    )
