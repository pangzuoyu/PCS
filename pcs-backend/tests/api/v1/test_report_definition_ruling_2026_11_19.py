"""**2026-11-19 人裁决落地** —— 报表定义的可见性 / 作废 / 工作区守卫。

## 四条裁决（本文件逐条钉住）

| # | 裁决 | 落到哪儿 |
|---|---|---|
| ① **TODO-192 #5** | **项目级定义的 `shared_with` 要生效** ⇒ ⇒ `CREATOR_ONLY`
  ⇒ ⇒ **只有创建人看得见** | `visible_clause` |
| ② **TODO-192 #10** | **SYSTEM_ADMIN 全局 bypass** ⇒ ⇒ 看得见**全部**
  （含别人的**草稿**）⇒ ⇒ 与 `require_project_access_or_404` 同口径 |
  `visible_clause` + 端点传 `roles` |
| ③ **TODO-190** | **作废的职责分离**：**已发布** ⇒ ⇒ 创建人**不能**自己作废（403）；
  **草稿** ⇒ ⇒ **创建人自己能删**（草稿只有创建人看得见 ⇒ ⇒ 全禁就没人能删自己的草稿） |
  `DefinitionService.obsolete` |
| ④ **TODO-192 #8** | **`POST /workspaces` 收 `project_id` ⇒ ⇒ 要有项目授权**
  （无权 ⇒ ⇒ 404） | `app/api/v1/workspaces.py` |

## 为什么全部用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ ④ 的断言在它上面是 **no-op**
⇒ ⇒ ⇒ 「端点缺项目守卫」这类缺陷**一个都测不出来**。

## 为什么每条都有**正对照**

只写「看不见」 ⇒ ⇒ 断言可能是**恒真**的（端点整个挂掉也绿）
⇒ ⇒ ⇒ 每条规则都配一条「该看得见的**确实**看得见」⇒ ⇒ 断言才**敏感**。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio

DEF_PATH = "/api/v1/report-builder/definitions"


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


async def _mk_project(db_session, name="裁决项目"):
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
                  project_id=None, shared_with="ALL_USERS", name="设备一览"):
    r = await strict_client.post(
        DEF_PATH,
        headers=_auth(subject, "DESIGNER", user_id=user_id),
        json=_body(project_id=str(project_id) if project_id else None,
                   shared_with=shared_with, name=name),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _publish_by_other(strict_client, def_id, *, subject="reviewer-1",
                             user_id, project_id=None):
    """由**别人**发布（创建人不能自审自批 —— TODO-172）。"""
    r = await strict_client.post(
        f"{DEF_PATH}/{def_id}/publish",
        headers=_auth(subject, "REVIEWER", user_id=user_id),
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# ① TODO-192 #5 · `shared_with` 对项目级也要生效
# ---------------------------------------------------------------------------


async def test_project_level_creator_only_is_invisible_to_other_members(
    strict_client, db_session, grant_project
):
    """⚠️ **项目级 + `CREATOR_ONLY` ⇒ ⇒ 项目内其他成员看不见**。

    ⇒ ⇒ 此前项目级那一档**不看 `shared_with`** ⇒ ⇒ `CREATOR_ONLY` 被
    **静默忽略** ⇒ ⇒ 「已发布 + CREATOR_ONLY」的项目级定义**人人可见**
    ⇒ ⇒ **字段与实现不符**。
    """
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="CREATOR_ONLY")
    await _publish_by_other(strict_client, d["def_id"], user_id=other)

    r = await strict_client.get(
        f"{DEF_PATH}/{d['def_id']}", headers=_auth("other-1", "DESIGNER", user_id=other))
    assert r.status_code == 404, r.text

    r = await strict_client.get(DEF_PATH, headers=_auth("other-1", "DESIGNER", user_id=other))
    assert d["def_id"] not in [i["def_id"] for i in r.json()["items"]]


async def test_project_level_creator_only_stays_visible_to_its_creator(
    strict_client, db_session, grant_project
):
    """**正对照**：创建人**自己**看得见（`CREATOR_ONLY` 不是「谁都看不见」）。"""
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="CREATOR_ONLY")
    await _publish_by_other(strict_client, d["def_id"], user_id=other)

    r = await strict_client.get(
        f"{DEF_PATH}/{d['def_id']}", headers=_auth("creator-1", "DESIGNER", user_id=creator))
    assert r.status_code == 200, r.text


async def test_project_level_all_users_is_visible_to_other_members(
    strict_client, db_session, grant_project
):
    """**正对照**：`ALL_USERS` 的项目级定义 ⇒ ⇒ 项目内其他成员**看得见**。

    ⚠️ 没有这条 ⇒ ⇒ 上面那条「看不见」可能是**恒真**的（整条规则挂了也绿）。
    """
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="ALL_USERS")
    await _publish_by_other(strict_client, d["def_id"], user_id=other)

    r = await strict_client.get(
        f"{DEF_PATH}/{d['def_id']}", headers=_auth("other-1", "DESIGNER", user_id=other))
    assert r.status_code == 200, r.text
    r = await strict_client.get(DEF_PATH, headers=_auth("other-1", "DESIGNER", user_id=other))
    assert d["def_id"] in [i["def_id"] for i in r.json()["items"]]


# ---------------------------------------------------------------------------
# ② TODO-192 #10 · SYSTEM_ADMIN 全局 bypass（可见性这一侧）
# ---------------------------------------------------------------------------


async def test_system_admin_sees_other_users_draft(strict_client, db_session):
    """⚠️ **admin 看得见别人的草稿**（与 `require_project_access_or_404` 同口径）。

    ⇒ ⇒ 此前 `visible_clause` **没有** admin 分支 ⇒ ⇒ 而 publish 的授权判定
    **有** ⇒ ⇒ 两处不一致 ⇒ ⇒ 症状是「admin 能 publish 却 GET 不到」。
    """
    creator = uuid.uuid4()
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator)

    r = await strict_client.get(
        f"{DEF_PATH}/{d['def_id']}", headers=_auth("admin-1", "SYSTEM_ADMIN"))
    assert r.status_code == 200, r.text
    r = await strict_client.get(DEF_PATH, headers=_auth("admin-1", "SYSTEM_ADMIN"))
    assert d["def_id"] in [i["def_id"] for i in r.json()["items"]]


async def test_ordinary_user_does_not_see_other_users_draft(strict_client, db_session):
    """**正对照**：普通用户**看不见**别人的草稿 ⇒ ⇒ 上面的 admin 是**特权**不是恒真。"""
    creator = uuid.uuid4()
    other = uuid.uuid4()
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator)

    r = await strict_client.get(
        f"{DEF_PATH}/{d['def_id']}", headers=_auth("other-1", "DESIGNER", user_id=other))
    assert r.status_code == 404, r.text
    r = await strict_client.get(DEF_PATH, headers=_auth("other-1", "DESIGNER", user_id=other))
    assert d["def_id"] not in [i["def_id"] for i in r.json()["items"]]


# ---------------------------------------------------------------------------
# ③ TODO-190 · 作废的职责分离
# ---------------------------------------------------------------------------


async def test_creator_cannot_obsolete_own_published_definition(
    strict_client, db_session, grant_project
):
    """⚠️ **已发布的定义 ⇒ ⇒ 创建人自己不能作废**（与 publish 同口径 ⇒ 403）。

    ⇒ ⇒ 此前 `obsolete()` **不查 `created_by`** ⇒ ⇒ 任何有项目授权的审核角色
    ⇒ ⇒ 都能作废**别人已发布**的定义 ⇒ ⇒ 打断别人的工作流。
    """
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)
    await _publish_by_other(strict_client, d["def_id"], user_id=other)

    r = await strict_client.post(
        f"{DEF_PATH}/{d['def_id']}/obsolete",
        headers=_auth("creator-1", "REVIEWER", user_id=creator),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_SELF_OBSOLETE_FORBIDDEN", r.text


async def test_reviewer_can_obsolete_other_users_published_definition(
    strict_client, db_session, grant_project
):
    """**正对照**：**别人**（有项目授权的审核角色）**能**作废已发布的定义。"""
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)
    await _publish_by_other(strict_client, d["def_id"], user_id=other)

    r = await strict_client.post(
        f"{DEF_PATH}/{d['def_id']}/obsolete",
        headers=_auth("reviewer-2", "REVIEWER", user_id=other),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "OBSOLETE", r.text


async def test_creator_can_obsolete_own_draft(
    strict_client, db_session, grant_project
):
    """⚠️ **草稿 ⇒ ⇒ 创建人自己能删**（草稿只有创建人看得见 ⇒ ⇒ 全禁就没人能删）。"""
    creator = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)

    r = await strict_client.post(
        f"{DEF_PATH}/{d['def_id']}/obsolete",
        headers=_auth("creator-1", "DESIGNER", user_id=creator),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "OBSOLETE", r.text


async def test_non_creator_cannot_obsolete_other_users_draft(
    strict_client, db_session, grant_project
):
    """⚠️ **别人的草稿 ⇒ ⇒ 404**（与「不存在」逐字同形 ⇒ ⇒ 不泄露存在性）。

    ⚠️ 判据**敏感**：执行者**有**项目授权 ⇒ ⇒ ⇒ 那个 404 只可能来自
    「草稿只有创建人能作废」这条 ⇒ ⇒ 删掉它 ⇒ ⇒ 这条断言就红。
    """
    creator = uuid.uuid4()
    other = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(other, project.project_id)

    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)

    r = await strict_client.post(
        f"{DEF_PATH}/{d['def_id']}/obsolete",
        headers=_auth("reviewer-2", "REVIEWER", user_id=other),
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# ④ TODO-192 #8 · POST /workspaces 的项目授权
# ---------------------------------------------------------------------------


async def test_create_workspace_with_unauthorized_project_is_404(
    strict_client, db_session
):
    """⚠️ **`POST /workspaces` 指向无授权的项目 ⇒ ⇒ 404**。

    ⇒ ⇒ 此前**收任意 `project_id` 且不查授权** ⇒ ⇒ 建出来的工作区行
    ⇒ ⇒ 指向一个我**看不见**的项目 ⇒ ⇒ 展示字段被污染。
    """
    me = uuid.uuid4()
    project = await _mk_project(db_session, name="别人的项目")   # **不**授权

    r = await strict_client.post(
        f"/api/v1/workspaces?owner_id={me}",
        headers=_auth("u1", "DESIGNER", user_id=me),
        json={"workspace_type": "FORMAL", "name": "越权工作区",
              "project_id": str(project.project_id)},
    )
    assert r.status_code == 404, r.text


async def test_create_workspace_with_authorized_project_is_201(
    strict_client, db_session, grant_project
):
    """**正对照**：有授权 ⇒ ⇒ 201（守卫不是「一律拒绝」）。"""
    me = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(me, project.project_id)

    r = await strict_client.post(
        f"/api/v1/workspaces?owner_id={me}",
        headers=_auth("u1", "DESIGNER", user_id=me),
        json={"workspace_type": "FORMAL", "name": "自己的工作区",
              "project_id": str(project.project_id)},
    )
    assert r.status_code == 201, r.text
    assert r.json()["project_id"] == str(project.project_id), r.text


async def test_create_personal_workspace_without_project_is_201(
    strict_client, db_session
):
    """**正对照**：**不挂项目**的个人工作区 ⇒ ⇒ 不该被项目守卫挡住（201）。"""
    me = uuid.uuid4()
    r = await strict_client.post(
        f"/api/v1/workspaces?owner_id={me}",
        headers=_auth("u1", "DESIGNER", user_id=me),
        json={"workspace_type": "PERSONAL", "name": "个人工作区"},
    )
    assert r.status_code == 201, r.text
