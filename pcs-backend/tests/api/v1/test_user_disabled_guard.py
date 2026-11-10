"""禁用用户不得访问物流面 —— P9B-4 T0-B（TODO-132）。

## 这个文件在钉什么

2026-11-10 实测：`UserProjectService.check_user_project_access` **只查
`UserProject` 行** ⇒ **不 join `users`** ⇒ 一个 `users.status = DISABLED`
的用户，只要手里还有一条**已发出的 access token**，仍能访问 20+ 物流端点。

⚠️ 真实登录路径在**发 token 时**拦禁用用户（`token_issuer` ⇒ 401），但
**已经发出的 token 仍然有效** ⇒ 「停用」形同虚设。

⇒ 本文件钉住：**每请求**在 **actor 层**判一次 `users.status`：

| 情形 | 期望 |
|---|---|
| `users.status = DISABLED` + 有授权行 | **401** `USER_DISABLED` |
| `users.status = ACTIVE` + 有授权行 | 放行（200） |
| `users` 表**没有该 user_id 的行** | 放行（mock 登录不落 users 表 · ADR-0046 §③b） |

## ⚠️ 三个连带点各有各的测试（漏一个就静默坏掉）

① `current_actor` 改 **async** ⇒ 直接 `await` 得 actor + 端点冒烟；
② `ws.py` 的**直接调用**（不走 `Depends`）⇒ WebSocket 握手仍通；
③ **mock 登录**（`users` 表无行）⇒ 仍能访问。

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ 在它上面「越权被拒」是空断言。
本文件用 `strict_client`（真守卫）⇒ 断言才有意义。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, User, Workspace

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


def _headers(username: str, role: str = "DESIGNER") -> dict[str, str]:
    token = create_access_token(subject=username, role=role)
    return {"Authorization": f"Bearer {token}"}


def _derived_user_id(username: str) -> uuid.UUID:
    """与 `current_actor` / `token_issuer` 一致：uuid5(NAMESPACE_DNS, username)。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, username)


async def _mk_user(db: AsyncSession, username: str, status: str) -> User:
    """造一行 `users`（`user_id` 用派生值 ⇒ 与 token 里的 `user_id` 对得上）。"""
    user = User(
        user_id=_derived_user_id(username),
        username=username,
        display_name=username,
        roles=["DESIGNER"],
        ad_groups=[],
        status=status,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        project = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession):
    async def _make(project: Project) -> Stream:
        stream = Stream(
            stream_id=uuid.uuid4(),
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            stream_name=f"S-{uuid.uuid4().hex[:6]}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            source="MANUAL",
            phase="LIQUID",
            temp=80.0,
            press=200.0,
            mass_flow=1000.0,
            composition_json={"7732-18-5": 1.0},
            approval_depth=1,
            sign_status="DRAFT",
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


# ---------------------------------------------------------------------------
# 核心：禁用用户的**既有 token** ⇒ 被拒
# ---------------------------------------------------------------------------


async def test_disabled_user_with_existing_token_is_rejected(
    strict_client, db_session, grant_project, make_project, make_stream
):
    """`users.status = DISABLED` + 有授权行 ⇒ 物流端点 **401**（不是 200、不是 404）。

    ⚠️ 断言 **code**：只断言状态码的话，「端点炸了返 500」也是非 200。
    """
    username = "disabled-designer"
    project = await make_project()
    await _mk_user(db_session, username, "DISABLED")
    await grant_project(_derived_user_id(username), project.project_id, username=username)
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}", headers=_headers(username)
    )
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "USER_DISABLED", r.text


async def test_active_user_with_existing_token_is_allowed(
    strict_client, db_session, grant_project, make_project, make_stream
):
    """对照组：同一用户 `ACTIVE` ⇒ **放行**（否则上面的 401 可能只是「守卫坏了」）。"""
    username = "active-designer"
    project = await make_project()
    await _mk_user(db_session, username, "ACTIVE")
    await grant_project(_derived_user_id(username), project.project_id, username=username)
    stream = await make_stream(project)

    r = await strict_client.get(
        f"/api/v1/streams/{stream.stream_id}", headers=_headers(username)
    )
    assert r.status_code == 200, r.text
    assert r.json()["stream_id"] == str(stream.stream_id)


async def test_user_without_users_row_is_allowed(
    strict_client, db_session, make_project, make_stream
):
    """⚠️ **users 表没有该 user_id 的行 ⇒ 放行**。

    为什么这条是**必须**的：mock 登录**不落 `users` 表**（ADR-0046 §③b）⇒
    判成 401 ⇒ **dev / E2E 的 mock 登录全线挂掉** ⇒ 而这个缺陷
    **只有 dev 环境跑起来才会发现**（单测里 mock 路由压根没挂）。

    ⇒ 这里用「mock 登录同款 token」（`issue_tokens(persist_user=False)`
    —— 走的正是 `/auth/mock-login` 的签发路径）+ 一个**不要求项目授权**的
    端点（`/api/v1/notifications`，鉴权身份就是 `recipient_id` 本身）。
    """
    from app.services.token_issuer import issue_tokens

    pair = await issue_tokens(
        username="mock-alice", role="DESIGNER", persist_user=False
    )
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    # 前置断言：mock 路径**确实没落** users 表
    row = (
        await db_session.execute(
            User.__table__.select().where(
                User.__table__.c.user_id == _derived_user_id("mock-alice")
            )
        )
    ).first()
    assert row is None, "mock 登录落了 users 表 ⇒ ADR-0046 §③b 被破坏"

    r = await strict_client.get("/api/v1/notifications", headers=headers)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 连带点 ①：`current_actor` 改 async
# ---------------------------------------------------------------------------


async def test_current_actor_is_awaitable(db_session):
    """直接 `await current_actor(...)` ⇒ 拿得到 actor（改 async 后的新契约）。"""
    from app.api.v1.config import current_actor

    token = create_access_token(subject="await-user", role="DESIGNER")
    actor = await current_actor(db_session, f"Bearer {token}")
    assert actor.username == "await-user"
    assert actor.role == "DESIGNER"
    assert actor.user_id == _derived_user_id("await-user")


_SMOKE_ENDPOINTS = [
    ("get", "/api/v1/streams/{sid}", None, 200),
    ("get", "/api/v1/streams/{sid}/properties", None, 200),
    ("get", "/api/v1/streams/{sid}/state-points", None, 200),
    ("get", "/api/v1/notifications", None, 200),
]


@pytest.mark.parametrize(
    "method,path,body,expected",
    _SMOKE_ENDPOINTS,
    ids=[c[1] for c in _SMOKE_ENDPOINTS],
)
async def test_endpoints_depending_on_current_actor_still_work(
    strict_client,
    db_session,
    grant_project,
    make_project,
    make_stream,
    method,
    path,
    body,
    expected,
):
    """⚠️ `current_actor` 被 **283 个端点**依赖 ⇒ 改 async / 加参数 ⇒
    任何一个端点的签名没跟上 ⇒ 那个端点直接 500。

    ⇒ 这里对**几个不同模块**的端点做正��冒烟（物流 / 属性 / 状态点 / 通知）。
    """
    username = "smoke-designer"
    project = await make_project()
    await _mk_user(db_session, username, "ACTIVE")
    await grant_project(_derived_user_id(username), project.project_id, username=username)
    stream = await make_stream(project)

    url = path.format(sid=stream.stream_id)
    if body is None:
        r = await getattr(strict_client, method)(url, headers=_headers(username))
    else:
        r = await getattr(strict_client, method)(url, json=body, headers=_headers(username))
    assert r.status_code == expected, f"{url}: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# 连带点 ②：`ws.py` 的**直接调用**（不走 `Depends` ⇒ 改 async 后不会自动适配）
#
# ⚠️ 那条用例放在**既有文件** `tests/api/v1/test_ws_notifications.py`
# （与 WS 相关的断言与 WS 用例放一起 ⇒ 漏改时容易看到）。
# ---------------------------------------------------------------------------
