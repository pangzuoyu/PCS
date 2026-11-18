"""**publish 的职责分离**（人裁决 2026-11-18 · TODO-172 / TODO-178）。

## 三条裁决（本文件逐条钉住）

| # | 裁决 | 落到哪儿 |
|---|---|---|
| ① | **审核者不能审自己创建的** | `created_by == actor` ⇒ ⇒ **403** |
| ② | **审核者需要对定义的项目有授权** | `project_id` 非空 ⇒ ⇒ 查 `user_projects` ⇒ ⇒ 无授权 ⇒ ⇒ **404**（与「不存在」同形） |
| ③ | **允许公司级审核者** | `project_id IS NULL`（公司级模板）⇒ ⇒ **不做项目判定** ⇒ ⇒ 任何审核角色（且非创建者）都能审 |

## 为什么 ① 与 ③ 不冲突

⇒ ⇒ **公司级模板**（`project_id IS NULL`）**没有项目可授权**
⇒ ⇒ ⇒ 若把 ② 无脑套上去 ⇒ ⇒ 公司级模板**永远没人能审**
⇒ ⇒ ⇒ ③ 就是「② 在公司级模板上不适用」的明写。

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ ② 的断言在它上面是 **no-op**
⇒ ⇒ ⇒ 「审核者没授权也照样能审」这类缺陷**一个都测不出来**。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _auth(subject: str, role: str = "DESIGNER", *, user_id: uuid.UUID | None = None):
    extra = {"user_id": str(user_id)} if user_id else None
    token = create_access_token(subject=subject, role=role, extra=extra)
    return {"Authorization": f"Bearer {token}"}


def _body(**over):
    body = {
        "project_id": None,
        "name": "设备一览",
        "category": "设备类",
        "description": "按位号列设备",
        "output_format": "xlsx",
        "shared_with": "ALL_USERS",
        "definition_json": {
            "DataSources": [{"source": "EQUIP_LIST"}],
            "SelectedFields": [
                {"source": "EQUIP_LIST", "field": "tag_number",
                 "alias": "位号", "order": 0, "visible": True},
            ],
            "FilterConditions": [],
        },
    }
    body.update(over)
    return body


async def _mk_project(db_session, name="审核项目"):
    from app.models.project import Project

    proj = Project(
        project_no=f"RPT-{uuid.uuid4().hex[:8]}",
        project_name=name, owner_company="X", location="X",
        project_type="CHEMICAL", design_phase="FEED", unit_system="SI",
        status="ACTIVE", workspace_id=uuid.uuid4(),
    )
    db_session.add(proj)
    await db_session.flush()
    return proj


async def _mk_def(strict_client, *, subject="author-1", user_id=None,
                  project_id=None):
    r = await strict_client.post(
        "/api/v1/report-builder/definitions",
        headers=_auth(subject, "DESIGNER", user_id=user_id),
        json=_body(project_id=str(project_id) if project_id else None),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# ① 审核者不能审自己创建的
# ---------------------------------------------------------------------------


async def test_creator_who_is_a_reviewer_cannot_publish_own_definition(
    strict_client, db_session, grant_project
):
    """⚠️ **创建人自己是 REVIEWER ⇒ ⇒ 也不能发布自己创建的**（裁决 ①）。

    ⇒ ⇒ 此前这条**没被守住**：既有用例的创建人是 DESIGNER ⇒ ⇒ 挡的是
    **角色闸**，不是「自审自批」⇒ ⇒ ⇒ 探针实测：创建人自己是 REVIEWER
    ⇒ ⇒ 发布自己创建的定义 ⇒ ⇒ **HTTP 200**（TODO-178）。
    """
    creator = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("creator-1", "REVIEWER", user_id=creator),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN", r.text


# ---------------------------------------------------------------------------
# ② 审核者需要对定义的项目有授权
# ---------------------------------------------------------------------------


async def test_reviewer_without_project_grant_cannot_publish(
    strict_client, db_session, grant_project
):
    """⚠️ **审核者对该项目没有授权 ⇒ ⇒ 404**（裁决 ② · 与「不存在」同形）。"""
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    d = await _mk_def(strict_client, subject="author-1", user_id=creator,
                      project_id=project.project_id)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert r.status_code == 404, r.text


async def test_reviewer_with_project_grant_can_publish(
    strict_client, db_session, grant_project
):
    """⚠️ **正面路径**：审核者**有**该项目的授权 ⇒ ⇒ 发布得下去。"""
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(reviewer, project.project_id)
    d = await _mk_def(strict_client, subject="author-1", user_id=creator,
                      project_id=project.project_id)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PUBLISHED"


# ---------------------------------------------------------------------------
# ③ 允许公司级审核者
# ---------------------------------------------------------------------------


async def test_company_level_definition_can_be_published_by_a_reviewer(
    strict_client, db_session
):
    """⚠️ **公司级模板（`project_id IS NULL`）⇒ ⇒ 审核者**不需要**项目授权**
    ⇒ ⇒ 只要**不是创建人**就能审（裁决 ③）。

    ⇒ ⇒ 否则公司级模板**永远没人能审** ⇒ ⇒ ⇒ ③ 就是 ② 的例外。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    d = await _mk_def(strict_client, subject="author-1", user_id=creator)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "PUBLISHED"


async def test_company_level_definition_creator_still_cannot_publish(
    strict_client, db_session
):
    """⚠️ **公司级模板也一样禁自审**（裁决 ① 对 ③ 同样成立）。"""
    creator = uuid.uuid4()
    d = await _mk_def(strict_client, subject="author-1", user_id=creator)

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("author-1", "REVIEWER", user_id=creator),
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# `update` 的项目授权（2026-11-18 · ce-code-review · TODO-192 #2 · P1）
# ---------------------------------------------------------------------------


async def test_update_cannot_repoint_a_definition_to_an_ungranted_project(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **创建人可把自己的定义改挂到没有授权的项目**（跨项目读的另一半）。

    ⇒ ⇒ `create()` 有 `require_project_access_or_404`（新建时不能挂到别人项目）
    ⇒ ⇒ **`update()` 此前没有** ⇒ ⇒ 创建人把自己 DRAFT 的定义
    ⇒ ⇒ **`PUT` 到一个自己没有授权的项目** ⇒ ⇒ 执行时 scope 就是那个项目
    ⇒ ⇒ ⇒ **跨项目读**（与 `create` 堵掉的是**同一条链**的两端）。

    ⇒ ⇒ 修法：与 `create` **对称** ⇒ ⇒ 无权 ⇒ ⇒ **404**（与「不存在」同形）。
    """
    creator = uuid.uuid4()
    my_project = await _mk_project(db_session, "我的项目")
    await grant_project(creator, my_project.project_id)
    d = await _mk_def(strict_client, subject="creator-2", user_id=creator,
                      project_id=my_project.project_id)

    other_project = await _mk_project(db_session, "别人的项目")

    r = await strict_client.put(
        f"/api/v1/report-builder/definitions/{d['def_id']}",
        headers=_auth("creator-2", "DESIGNER", user_id=creator),
        json=_body(project_id=str(other_project.project_id)),
    )
    assert r.status_code == 404, (
        f"改挂到无授权项目必须是 404（与「不存在」同形）⇒ ⇒ 拿到了 {r.status_code}"
        f" ⇒ ⇒ 跨项目读：{r.text}"
    )
