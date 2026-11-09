"""`strict_client` fixture 本身的测试 —— P9B-4 紧急批次 T1。

## 这个文件在钉什么

「**端点缺项目守卫**」这类缺陷**测不出来**的根因：`tests/conftest.py` 的
`client` fixture 把 `UserProjectService.check_user_project_access` **mock 成
永远 True** ⇒ 任何「越权被拒」的断言在它上面都是**空断言**（守卫压根没跑）。

⇒ 本文件把「两套 client 的差别」**钉成事实**：

- `strict_client` ⇒ 无授权行 ⇒ **404**（守卫真跑了）
- `client` ⇒ 无授权行 ⇒ **200**（守卫被 mock 掉了）

⚠️ **第二条是故意记录一个「缺陷」的**（旧 client 测不到守卫缺陷）—— **别删**。
它存在的意义是：让后人**知道**默认 client 不严格，从而**主动**选 `strict_client`。
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
def designer_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='designer-user', role='DESIGNER')}"
    }


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    """`designer-user` 派生 UUID（与 `current_actor` 一致：uuid5(DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, "designer-user")


async def _make_project(db_session) -> uuid.UUID:
    """建一个**没有授权行**的项目。"""
    from app.models.project import Project, Workspace

    workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            name="WS",
            status="ACTIVE",
        )
    )
    await db_session.commit()

    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id,
            workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}",
            project_name="测试项目",
            owner_company="PCS",
            location="惠州",
            project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN",
            unit_system="SI",
        )
    )
    await db_session.commit()
    return project_id


async def test_strict_client_rejects_a_user_without_project_grant(
    strict_client, db_session, designer_headers
):
    """`strict_client` 不 mock 守卫 ⇒ 无授权行的用户 ⇒ **404**（不是 200）。"""
    project_id = await _make_project(db_session)

    r = await strict_client.get(
        f"/api/v1/projects/{project_id}/streams", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_strict_client_allows_a_user_with_project_grant(
    strict_client, db_session, designer_headers, designer_user_id, grant_project
):
    """有授权行 ⇒ **200** ⇒ 证明上面那条 404 不是「端点坏了」。"""
    project_id = await _make_project(db_session)
    await grant_project(designer_user_id, project_id, username="designer-user")

    r = await strict_client.get(
        f"/api/v1/projects/{project_id}/streams", headers=designer_headers
    )
    assert r.status_code == 200, r.text


async def test_legacy_client_bypasses_the_guard(
    client, db_session, designer_headers
):
    """⚠️ 旧 `client` 把守卫 mock 成永远 True ⇒ 同条件下 **200**。

    这条测试是**故意**记录一个缺陷（守卫缺陷用默认 client 测不出来）—— **别删**。
    """
    project_id = await _make_project(db_session)

    r = await client.get(
        f"/api/v1/projects/{project_id}/streams", headers=designer_headers
    )
    assert r.status_code == 200, r.text


async def test_strict_client_stays_strict_even_when_the_legacy_client_is_requested(
    client, strict_client, db_session, designer_headers
):
    """⚠️ **同一个测试里既请求 `client` 又请求 `strict_client`** ⇒
    `client` 的 monkeypatch 会让守卫被 mock 掉 ⇒ `strict_client` 仍必须**严格**。

    这是「守卫测试假绿」的**头号来源** ⇒ 所以 `strict_client` 在**每次请求前**
    把守卫还原成真身 ⇒ 无论 fixture 的建立顺序如何。
    """
    project_id = await _make_project(db_session)

    r = await strict_client.get(
        f"/api/v1/projects/{project_id}/streams", headers=designer_headers
    )
    assert r.status_code == 404, (
        f"守卫被 `client` 的 mock 掉了 ⇒ 守卫测试会假绿：{r.text}"
    )
