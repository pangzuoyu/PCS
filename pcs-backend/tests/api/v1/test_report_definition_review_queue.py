"""「待我审核」队列 —— **只读视图**（2026-11-23 · P10-I · T1 · TODO-197）。

## 它解的是哪个洞

「创建 ⇒ 交给审核者 ⇒ 审核者发布」这条链，**在 UI 上断在第二环**：

| 环节 | 代码事实 | 结果 |
|---|---|---|
| 创建人发布 | `publish()` **禁自审 403** | ❌ |
| 审核者找到草稿 | `visible_clause`：草稿**只有创建人可见** | ❌ 列表页看不见 |
| ⇒ ⇒ | ⇒ ⇒ | **「发布」按钮对所有角色 100% 死** |

⇒ ⇒ 本文件钉住队列的**每一条过滤规则**（人裁约束 2）+ `publish()` 的
**`CREATOR_ONLY` 补判**（人裁 ①）。

## 口径（人裁 2026-11-23 · 约束 2）

| 草稿类型 | 审核者可见 | 条件 |
|---|---|---|
| 公司级（`project_id IS NULL`）| ✔ | `REVIEWER+` |
| 项目级 | ✔ | `REVIEWER+` ∧ 我在该项目有 `user_projects` 授权 |
| 项目级 · 我无授权 | ✘ | ——（即使我是 `REVIEWER`）|
| `created_by == 我` | ✘ | ——（自审禁止 ⇒ 与 `publish()` 的 **403** 一致）|
| `shared_with == CREATOR_ONLY` | ✘ | ——（它没有「发布」这个动作）|

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 「无授权也出现在队列里」
这类缺陷在它上面**一个都测不出来**。

## ⚠️ **为什么 URL 字面量写在每个测试函数体内**

`tests/test_strict_client_ratchet.py` 的 `_strict_client_urls()` 用 AST
**逐个测试函数**扫 URL 字面量 ⇒ ⇒ 写在模块级常量或 helper 里 ⇒ ⇒
⇒ 棘轮**扫不到** ⇒ ⇒ ⇒ 台账会说「这个端点没有 strict_client 断言」⇒ ⇒ ⇒ 红。
⇒ ⇒ 所以下面每处都**写全路径**（不是引常量）。
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
                  project_id=None, shared_with="ALL_USERS"):
    r = await strict_client.post(
        "/api/v1/report-builder/definitions",
        headers=_auth(subject, "DESIGNER", user_id=user_id),
        json=_body(
            project_id=str(project_id) if project_id else None,
            shared_with=shared_with,
        ),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _ids(payload: dict) -> set[str]:
    return {item["def_id"] for item in payload["items"]}


# ---------------------------------------------------------------------------
# ① 公司级草稿 ⇒ 审核者看得见
# ---------------------------------------------------------------------------


async def test_company_level_draft_appears_in_the_review_queue(
    strict_client, db_session
):
    """⚠️ **公司级模板（`project_id IS NULL`）⇒ ⇒ 审核者不需要项目授权也能看见**。

    ⇒ ⇒ 这是队列存在的**最小**场景（没有项目 ⇒ 没有授权行可查）。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator)

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer))
    assert r.status_code == 200, r.text
    assert d["def_id"] in _ids(r.json()), r.text


# ---------------------------------------------------------------------------
# ② 项目级草稿 ⇒ 有授权才看得见（**成对断**）
# ---------------------------------------------------------------------------


async def test_project_level_draft_appears_only_with_a_project_grant(
    strict_client, db_session, grant_project
):
    """⚠️ **成对断**：同一条草稿 ⇒ ⇒ **有授权 ⇒ 出现** · **无授权 ⇒ 不出现**。

    ⇒ ⇒ 只断「有授权 ⇒ 出现」是**假绿**：过滤若根本没生效，它照样绿。
    """
    creator = uuid.uuid4()
    with_grant = uuid.uuid4()
    without_grant = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(with_grant, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)

    r_ok = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("rev-ok", "REVIEWER", user_id=with_grant))
    assert r_ok.status_code == 200, r_ok.text
    assert d["def_id"] in _ids(r_ok.json()), r_ok.text

    r_no = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("rev-no", "REVIEWER", user_id=without_grant))
    assert r_no.status_code == 200, r_no.text
    assert d["def_id"] not in _ids(r_no.json()), (
        "没有该项目授权的审核者**看到了**该项目的草稿 ⇒ ⇒ 跨项目读")


# ---------------------------------------------------------------------------
# ③ 自己的草稿不进队列（自审禁止 ⇒ 点了必失败）
# ---------------------------------------------------------------------------


async def test_own_draft_never_appears_in_the_review_queue(
    strict_client, db_session
):
    """⚠️ **创建人自己是 REVIEWER ⇒ ⇒ 队列里也不能有他的草稿**。

    ⇒ ⇒ `publish()` 禁自审（403）⇒ ⇒ 列出来就是「**点了必失败的按钮**」。
    """
    creator = uuid.uuid4()
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator)

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("creator-1", "REVIEWER", user_id=creator))
    assert r.status_code == 200, r.text
    assert d["def_id"] not in _ids(r.json()), r.text


async def test_system_admin_does_not_see_own_draft_in_the_review_queue(
    strict_client, db_session
):
    """⚠️ **SYSTEM_ADMIN 也排除自己的草稿**（hermes A-4）。

    ⇒ ⇒ SYSTEM_ADMIN 有全局 bypass（`visible_clause`）⇒ ⇒ 若队列复用它
    ⇒ ⇒ admin 会把**别人的 `CREATOR_ONLY` 草稿**也列进来
    ⇒ ⇒ ⇒ 且自己的草稿也会列出来 ⇒ ⇒ 「点了必失败的按钮」。
    """
    admin = uuid.uuid4()
    d = await _mk_def(strict_client, subject="admin-1", user_id=admin)

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("admin-1", "SYSTEM_ADMIN", user_id=admin))
    assert r.status_code == 200, r.text
    assert d["def_id"] not in _ids(r.json()), r.text


# ---------------------------------------------------------------------------
# ④ `CREATOR_ONLY` 的草稿不进队列（人裁 ①）
# ---------------------------------------------------------------------------


async def test_creator_only_draft_never_appears_in_the_review_queue(
    strict_client, db_session, grant_project
):
    """⚠️ **`CREATOR_ONLY`（仅创建人可见）的草稿不进队列**（人裁 ①）。

    ⇒ ⇒ 它的含义是「**不给别人看**」⇒ ⇒ 发布出来**也没别人看得见**
    ⇒ ⇒ ⇒ 它**没有「发布」这个动作**⇒ ⇒ 与 `publish()` 的补判**同一判据**。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(reviewer, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="CREATOR_ONLY")

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer))
    assert r.status_code == 200, r.text
    assert d["def_id"] not in _ids(r.json()), (
        "仅创建人可见的草稿出现在队列里 ⇒ ⇒ 审核者能发布它 ⇒ ⇒ 洞没堵")


# ---------------------------------------------------------------------------
# ⑤ 角色闸：非审核角色 ⇒ 403
# ---------------------------------------------------------------------------


async def test_non_reviewer_role_is_forbidden_on_the_queue(
    strict_client, db_session
):
    """⚠️ **DESIGNER 看不到队列**（403 · `REPORT_DEFINITION_ROLE_REQUIRED`）。

    ⚠️ **为什么不是「空列表」**：队列的过滤是「**谁能审**」
    ⇒ ⇒ 闸门与过滤**同处 service 层** ⇒ ⇒ 端点漏调也绕不过。
    """
    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("designer-1", "DESIGNER", user_id=uuid.uuid4()))
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_ROLE_REQUIRED", r.text


# ---------------------------------------------------------------------------
# ⑥ 队列只返元数据（**不带正文**）
# ---------------------------------------------------------------------------


async def test_queue_returns_metadata_only(strict_client, db_session):
    """⚠️ **队列不返 `definition_json`**（人裁约束 1：只读视图 · 不进编辑器）。

    ⇒ ⇒ 报表正文是**半成品**⇒ ⇒ 审核者只需知道「有什么要审」⇒ ⇒
    ⇒ ⇒ 正文不进队列。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator)

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer))
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i["def_id"] == d["def_id"])
    assert "definition_json" not in item, item
    assert set(item) == {
        "def_id", "name", "category", "description",
        "created_by", "project_id", "created_at", "updated_at",
    }, item


# ---------------------------------------------------------------------------
# ⑦ `publish()` 补判 `shared_with`（人裁 ① · 服务层那一条）
# ---------------------------------------------------------------------------


async def test_publishing_a_creator_only_draft_is_forbidden(
    strict_client, db_session, grant_project
):
    """⚠️ **`CREATOR_ONLY` 的草稿不能由他人发布**（403 · `REPORT_DEFINITION_NOT_SHAREABLE`）。

    ⇒ ⇒ 此前 `publish()` **不判 `shared_with`** ⇒ ⇒ 任何审核角色都能把它发掉
    ⇒ ⇒ ⇒ 发布后**仍只有创建人看得见**⇒ ⇒ 那是一次**对别人不可见的动作**。
    ⇒ ⇒ ⇒ 「队列一上 UI 就给它开了口子」⇒ ⇒ ⇒ 洞在**服务层**堵。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(reviewer, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="CREATOR_ONLY")

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_NOT_SHAREABLE", r.text


async def test_creator_only_draft_is_404_when_project_access_is_missing(
    strict_client, db_session, grant_project
):
    """⚠️ **无权访问该项目 ⇒ ⇒ 404 先赢**（不是 403）。

    ⇒ ⇒ 403 的文案会说明「这条存在但不能发」⇒ ⇒ 那泄露了**半成品的存在性**
    ⇒ ⇒ ⇒ 无权的人应当只看到「不存在」（404 · 与「不存在」逐字同形）。
    """
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id, shared_with="CREATOR_ONLY")

    r = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "REPORT_DEFINITION_NOT_FOUND", r.text


# ---------------------------------------------------------------------------
# ⑧ 队列只列草稿（已发布的不列）
# ---------------------------------------------------------------------------


async def test_published_definitions_are_not_in_the_queue(
    strict_client, db_session, grant_project
):
    """⚠️ **已发布的定义不进队列**（队列 = 「待审」，不是「全部定义」）。"""
    creator = uuid.uuid4()
    reviewer = uuid.uuid4()
    project = await _mk_project(db_session)
    await grant_project(creator, project.project_id)
    await grant_project(reviewer, project.project_id)
    d = await _mk_def(strict_client, subject="creator-1", user_id=creator,
                      project_id=project.project_id)

    rp = await strict_client.post(
        f"/api/v1/report-builder/definitions/{d['def_id']}/publish",
        headers=_auth("reviewer-1", "REVIEWER", user_id=reviewer),
    )
    assert rp.status_code == 200, rp.text

    r = await strict_client.get(
        "/api/v1/report-builder/definitions/pending-review",
        headers=_auth("reviewer-2", "REVIEWER", user_id=uuid.uuid4()))
    assert r.status_code == 200, r.text
    assert d["def_id"] not in _ids(r.json()), r.text
