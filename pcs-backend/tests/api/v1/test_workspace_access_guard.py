"""**工作区访问守卫** —— P10-F · F3 修复批（TODO-179 / 180 / 182 / 185 / 186）。

## 为什么要有这个文件

F3 守卫覆盖审计查出**两条 critical**，它们是**同一条链的两端**：

| 端点 | 审计结论 |
|---|---|
| `GET /workspaces`（等 3 个） | **TODO-186** |
| `GET /records/piping`（等 3 个） | **TODO-179** |

⇒ ⇒ `workspaces` 的三个端点：**不要求登录** ⇒ ⇒ 匿名可枚举**全部** workspace
（`owner_id` 不传即全量）⇒ ⇒ 匿名 GET 还**写库**（`touch`）⇒ ⇒ 匿名 POST 可
指定**任意 `owner_id`** ⇒ ⇒ **审计行也记在那个 owner 名下**。

⇒ ⇒ `records` 的三个端点：**不要求登录、也不做项目授权** ⇒ ⇒ 匿名可读走
**任意项目**的管路记录与变更快照。

⇒ ⇒ **前者把 `workspace_id` 白送给攻击者，后者用 `workspace_id` 换走业务数据**
⇒ ⇒ ⇒ **匿名可读走任意项目的业务数据**。

## 本文件钉的规则（**口径来自人裁决 2026-11-18 · TODO-169**）

> **A FORMAL workspace belongs to exactly one project; a workspace that belongs
> to no project is PERSONAL.**（`CONCEPTS.md` §Workspaces）

⇒ ⇒ ⇒ **工作区的访问权口径**：

| 工作区 | 谁能访问 |
|---|---|
| 有项目（FORMAL） | 对该项目**有 `user_projects` 授权行**的人（SYSTEM_ADMIN 全局 bypass） |
| 无项目（PERSONAL） | **owner 本人** |
| 不属于任何人 | **404**（登录了也不行）⇒ ⇒ ⇒ 「登录」是**下限**，不是授权 |

⇒ ⇒ **无权 ⇒ ⇒ 404**（与「不存在」**逐字同形** ⇒ ⇒ 枚举不出 UUID）。

## ⚠️ 「有项目」怎么判定（**2026-11-18 · P10-F 评审的 P0 修**）

**真相源 = `projects.workspace_id`（反查）**，**不是** `workspaces.project_id` ——
后者在生产路径上**从来不写**（`POST /projects` 只写 `Project(workspace_id=...)`）
⇒ ⇒ 拿它当分档键 ⇒ ⇒ **把 FORMAL 工作区当成 PERSONAL** ⇒ ⇒
项目的其他成员读管路记录 ⇒ **404**；`POST /records/piping` ⇒ **恒 400**。

⇒ ⇒ 本文件的夹具**照生产形状造**（工作区先建、项目后建、**再回填**
`workspace.project_id`）⇒ ⇒ **不再手造「生产不存在的形状」**
⇒ ⇒ 这正是「替身比被测物更宽容」那条教训。

## 为什么用 `strict_client`

默认 `client` 把项目守卫 mock 成永远 True ⇒ ⇒ 在它上面「越权被拒」是**空断言**
⇒ ⇒ 本文件**全部**用 `strict_client`（真守卫）。
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


def _tok(user_id: uuid.UUID, role: str = "DESIGNER") -> dict[str, str]:
    token = create_access_token(
        subject=str(user_id), role=role, extra={"user_id": str(user_id)}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mk_ws(db_session, *, owner_id, workspace_type="FORMAL"):
    """建一个工作区（**生产形状**：此时**还没有项目** ⇒ `project_id` 留空）。"""
    from app.models.project import Workspace

    ws = Workspace(
        workspace_id=uuid.uuid4(),
        workspace_type=workspace_type,
        owner_id=owner_id,
        name="guard-test",
        status="ACTIVE",
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return ws


async def _mk_project_on(db_session, ws, label: str = "P") -> uuid.UUID:
    """在 `ws` 上建一个项目（**生产形状**：`Project.workspace_id` 指向该工作区）。

    ⚠️ **故意**不填 `workspaces.project_id` ⇒ ⇒ 守卫**不许依赖那一列的冗余副本**
    ⇒ ⇒ 真相源只能是**反查 `projects.workspace_id`**。

    ⚠️ **为什么不是「照生产填上」**：`POST /projects` 现在会回填那一列
    （`test_creating_a_project_binds_the_workspace_to_it` 钉着它）
    ⇒ ⇒ 但守卫**不能因此就依赖它** ⇒ ⇒ 存量数据、人工改动、迁移漏跑
    ⇒ ⇒ 都会让那一列与真相不一致 ⇒ ⇒ **夹具故意造出「列没跟上」的样子**
    ⇒ ⇒ 这样「把守卫改回按那一列判」的变异**必须变红**（变异敏感）。

    ⇒ ⇒ 「夹具比被测物宽容」这条教训的反面：**夹具要能证伪守卫**。
    """
    from app.models.project import Project

    pid = uuid.uuid4()
    db_session.add(Project(
        project_id=pid, project_no=f"P-{label}-{pid.hex[:6]}", project_name=label,
        owner_company="t", location="t", project_type="test",
        design_phase="BASIC", unit_system="SI", status="ACTIVE",
        workspace_id=ws.workspace_id))
    await db_session.commit()
    return pid


async def _mk_project(db_session, label: str = "P") -> uuid.UUID:
    from app.models.project import Project

    pid = uuid.uuid4()
    db_session.add(Project(
        project_id=pid, project_no=f"P-{label}-{pid.hex[:6]}", project_name=label,
        owner_company="t", location="t", project_type="test",
        design_phase="BASIC", unit_system="SI", status="ACTIVE",
        workspace_id=uuid.uuid4()))
    await db_session.flush()
    return pid


async def _mk_pipe(strict_client, db_session, *, ws, project_id, user_id) -> str:
    """在 `ws` 里造一条管路记录（**走 API** ⇒ ⇒ 守卫是真的）。"""
    r = await strict_client.post(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        json={
            "project_id": str(project_id),
            "line_no": "P-100",
            "norm_oper_press": 1.0, "max_oper_press": 1.5,
            "norm_oper_temp": 40.0, "max_oper_temp": 80.0,
            "design_press": 2.0, "design_temp": 100.0,
            "piping_category": "GC2", "pressure_test_medium": "WATER",
            "pressure_test_press": 3.0, "check_class": "II",
        },
        headers=_tok(user_id),
    )
    assert r.status_code == 200, r.text
    return r.json()["pipe_id"]


# ---------------------------------------------------------------------------
# `workspaces.py`（TODO-186）
# ---------------------------------------------------------------------------


async def test_workspaces_list_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得列出工作区**（TODO-186）⇒ ⇒ 这是枚举的入口。"""
    await _mk_ws(db_session, owner_id=uuid.uuid4())
    r = await strict_client.get("/api/v1/workspaces")
    assert r.status_code == 401, r.text


async def test_workspaces_list_without_owner_id_is_admin_only(strict_client, db_session):
    """⚠️ **`owner_id` 不传 = admin 视图**（前端注释原话）⇒ ⇒ 那就得是 admin。

    ⇒ ⇒ 非 admin 不传 `owner_id` ⇒ ⇒ **403**（不是「默默给全量」）。
    """
    me = uuid.uuid4()
    await _mk_ws(db_session, owner_id=me)
    r = await strict_client.get("/api/v1/workspaces", headers=_tok(me))
    assert r.status_code == 403, r.text

    admin = await strict_client.get(
        "/api/v1/workspaces", headers=_tok(me, "SYSTEM_ADMIN"))
    assert admin.status_code == 200, admin.text


async def test_workspaces_list_of_another_user_is_forbidden(strict_client, db_session):
    """⚠️ **普通用户不得列别人的工作区**（admin 除外）。"""
    me, other = uuid.uuid4(), uuid.uuid4()
    await _mk_ws(db_session, owner_id=other)
    r = await strict_client.get(
        f"/api/v1/workspaces?owner_id={other}", headers=_tok(me))
    assert r.status_code == 403, r.text


async def test_workspaces_list_of_own_workspaces_is_allowed(strict_client, db_session):
    """⚠️ **正面路径**：列自己的 ⇒ ⇒ 200。"""
    me = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=me)
    r = await strict_client.get(
        f"/api/v1/workspaces?owner_id={me}", headers=_tok(me))
    assert r.status_code == 200, r.text
    assert str(ws.workspace_id) in {w["workspace_id"] for w in r.json()}


async def test_workspace_detail_of_another_users_workspace_is_404(
    strict_client, db_session
):
    """⚠️ **无权读别人的工作区 ⇒ ⇒ 404**（与「不存在」同形 ⇒ ⇒ 不泄露存在性）。"""
    other = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=other)
    r = await strict_client.get(
        f"/api/v1/workspaces/{ws.workspace_id}", headers=_tok(uuid.uuid4()))
    assert r.status_code == 404, r.text

    # ⚠️ **逐字同形**：与「真不存在」的响应**一模一样**
    missing = await strict_client.get(
        f"/api/v1/workspaces/{uuid.uuid4()}", headers=_tok(uuid.uuid4()))
    assert missing.status_code == 404
    assert r.json()["code"] == missing.json()["code"], (
        "无权与不存在的错误码不同 ⇒ ⇒ 枚举得出 UUID 是否存在"
    )


async def test_workspace_detail_of_own_workspace_is_200(strict_client, db_session):
    me = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=me)
    r = await strict_client.get(
        f"/api/v1/workspaces/{ws.workspace_id}", headers=_tok(me))
    assert r.status_code == 200, r.text


async def test_workspace_create_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得建工作区**（TODO-186）⇒ ⇒ 否则可无限制造行 + 写审计。"""
    r = await strict_client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(uuid.uuid4())},
        json={"workspace_type": "PERSONAL", "name": "anon"},
    )
    assert r.status_code == 401, r.text


async def test_workspace_create_cannot_impersonate_another_owner(
    strict_client, db_session
):
    """⚠️ **`owner_id` 由客户端指定 ⇒ ⇒ 审计行记在别人名下**（审计污染）。"""
    me, victim = uuid.uuid4(), uuid.uuid4()
    r = await strict_client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(victim)},
        json={"workspace_type": "PERSONAL", "name": "forged"},
        headers=_tok(me),
    )
    assert r.status_code == 403, r.text

    from sqlalchemy import select

    from app.models.system import AuditLog

    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.user_id == victim)
    )).scalars().all()
    assert not rows, "审计行记在了伪造的 owner 名下 ⇒ ⇒ 审计污染"


async def test_workspace_create_uses_the_token_identity(strict_client, db_session):
    """⚠️ **正面路径**：建出来的工作区归**令牌里的那个人**。"""
    me = uuid.uuid4()
    r = await strict_client.post(
        "/api/v1/workspaces",
        params={"owner_id": str(me)},
        json={"workspace_type": "PERSONAL", "name": "mine"},
        headers=_tok(me),
    )
    assert r.status_code == 201, r.text
    assert r.json()["owner_id"] == str(me)


# ---------------------------------------------------------------------------
# `records.py`（TODO-179 / 180 / 182 / 185）
# ---------------------------------------------------------------------------


async def test_records_list_requires_authentication(strict_client, db_session):
    """⚠️ **匿名不得读管路记录**（TODO-179）。"""
    me = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=me)
    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}")
    assert r.status_code == 401, r.text


async def test_records_list_of_another_projects_workspace_is_404(
    strict_client, db_session, grant_project
):
    """⚠️ **对别人项目的 FORMAL 工作区 ⇒ ⇒ 404**（与「不存在」同形）。"""
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "victim")
    await grant_project(owner, project)   # owner 有授权 ⇒ ⇒ 能建记录
    await _mk_pipe(strict_client, db_session, ws=ws, project_id=project,
                   user_id=owner)

    attacker = uuid.uuid4()
    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        headers=_tok(attacker))
    assert r.status_code == 404, r.text

    missing = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={uuid.uuid4()}",
        headers=_tok(attacker))
    assert missing.status_code == 404
    assert r.json()["code"] == missing.json()["code"], (
        "无权与不存在的错误码不同 ⇒ ⇒ 枚举得出 workspace 是否存在"
    )


async def test_records_list_of_authorized_project_is_200(
    strict_client, db_session, grant_project
):
    """⚠️ **正面路径**：对该项目有授权 ⇒ ⇒ 200 + 看到行。"""
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "mine")
    await grant_project(owner, project)
    await _mk_pipe(strict_client, db_session, ws=ws, project_id=project,
                   user_id=owner)

    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        headers=_tok(owner))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


async def test_records_list_of_own_personal_workspace_is_200(
    strict_client, db_session
):
    """⚠️ **PERSONAL 工作区（无项目）⇒ ⇒ owner 本人可读**（TODO-169 的口径）。"""
    me = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=me, workspace_type="PERSONAL")
    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        headers=_tok(me))
    assert r.status_code == 200, r.text


async def test_records_list_of_another_personal_workspace_is_404(
    strict_client, db_session
):
    """⚠️ **PERSONAL 工作区也不是公共的** ⇒ ⇒ 别人的 ⇒ ⇒ 404。"""
    other = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=other, workspace_type="PERSONAL")
    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        headers=_tok(uuid.uuid4()))
    assert r.status_code == 404, r.text


async def test_records_detail_and_snapshots_of_another_project_are_404(
    strict_client, db_session, grant_project
):
    """⚠️ **详情与快照端点同样要守**（TODO-185：详情端点此前**零测试**）。"""
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "victim2")
    await grant_project(owner, project)
    pipe_id = await _mk_pipe(strict_client, db_session, ws=ws,
                             project_id=project, user_id=owner)

    attacker = uuid.uuid4()
    detail = await strict_client.get(
        f"/api/v1/records/piping/{pipe_id}?workspace_id={ws.workspace_id}",
        headers=_tok(attacker))
    assert detail.status_code == 404, detail.text

    snaps = await strict_client.get(
        f"/api/v1/records/piping/{pipe_id}/snapshots"
        f"?workspace_id={ws.workspace_id}",
        headers=_tok(attacker))
    assert snaps.status_code == 404, snaps.text


async def test_records_detail_of_own_record_is_200(
    strict_client, db_session, grant_project
):
    """⚠️ **正面路径**：详情端点对有权者 ⇒ ⇒ 200（**补上零测试的洞**）。"""
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "mine2")
    await grant_project(owner, project)
    pipe_id = await _mk_pipe(strict_client, db_session, ws=ws,
                             project_id=project, user_id=owner)

    r = await strict_client.get(
        f"/api/v1/records/piping/{pipe_id}?workspace_id={ws.workspace_id}",
        headers=_tok(owner))
    assert r.status_code == 200, r.text
    assert r.json()["pipe_id"] == pipe_id


async def test_records_create_rejects_project_mismatch(
    strict_client, db_session, grant_project
):
    """⚠️ **`payload.project_id` 与工作区的项目不一致 ⇒ ⇒ 400**（TODO-180）。

    ⇒ ⇒ 否则「授权在项目 A 的人把记录写进项目 B 的工作区」。
    """
    me = uuid.uuid4()
    project_a = await _mk_project(db_session, "A")
    ws_b = await _mk_ws(db_session, owner_id=uuid.uuid4())
    project_b = await _mk_project_on(db_session, ws_b, "B")
    # ⚠️ **对 B 有授权**（否则先吃 404 ⇒ ⇒ 那是**授权**问题，不是**一致性**问题）
    await grant_project(me, project_b)

    r = await strict_client.post(
        f"/api/v1/records/piping?workspace_id={ws_b.workspace_id}",
        json={
            "project_id": str(project_a),
            "line_no": "P-100",
            "norm_oper_press": 1.0, "max_oper_press": 1.5,
            "norm_oper_temp": 40.0, "max_oper_temp": 80.0,
            "design_press": 2.0, "design_temp": 100.0,
            "piping_category": "GC2", "pressure_test_medium": "WATER",
            "pressure_test_press": 3.0, "check_class": "II",
        },
        headers=_tok(me),
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 「工作区 ↔ 项目」的绑定（2026-11-18 · P10-F 评审的 **P0** 修）
# ---------------------------------------------------------------------------


async def test_records_list_of_authorized_project_member_is_200(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **回归钉子（P0）**：**项目的其他成员**（有 `user_projects` 授权行）
    ⇒ ⇒ 读**别人 owner 的 FORMAL 工作区**里的管路记录 ⇒ ⇒ **200**。

    ⚠️ **这条在修之前是 404** ⇒ ⇒ 因为守卫拿 `workspaces.project_id` 当分档键
    ⇒ ⇒ 而那一列**生产路径从来不写** ⇒ ⇒ FORMAL 工作区被当成 PERSONAL
    ⇒ ⇒ 只有 owner 本人能进 ⇒ ⇒ **项目的其他成员被挡在门外**。

    ⇒ ⇒ 这条测试的意义：**走生产形状**（工作区 → 项目 → 回填）⇒ ⇒
    ⇒ ⇒ 断言的是「成员能读到」而不是「夹具凑出来的形状能读到」。
    """
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "shared")
    await grant_project(owner, project)
    await _mk_pipe(strict_client, db_session, ws=ws, project_id=project,
                   user_id=owner)

    member = uuid.uuid4()
    await grant_project(member, project)   # 成员：对项目有授权

    r = await strict_client.get(
        f"/api/v1/records/piping?workspace_id={ws.workspace_id}",
        headers=_tok(member))
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


async def test_workspace_detail_of_authorized_project_member_is_200(
    strict_client, db_session, grant_project
):
    """⚠️⚠️ **同一条 P0** 的另一面：工作区详情端点对**项目成员**也要放行。"""
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    project = await _mk_project_on(db_session, ws, "shared2")
    await grant_project(owner, project)

    member = uuid.uuid4()
    await grant_project(member, project)

    r = await strict_client.get(
        f"/api/v1/workspaces/{ws.workspace_id}", headers=_tok(member))
    assert r.status_code == 200, r.text


async def test_workspace_with_two_projects_is_409(strict_client, db_session):
    """⚠️ **歧义 ⇒ ⇒ fail-loud（409）**，不是随便挑一个项目。

    ⇒ ⇒ 「一个工作区挂两个项目」违反 TODO-169 的口径（FORMAL 恰好一个）
    ⇒ ⇒ 挑一个 ⇒ 「授权在 A 的人」可能因为挑到 B 被拒（或反之）⇒ ⇒ 更糟。
    """
    from app.models.project import Project

    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    await _mk_project_on(db_session, ws, "amb1")
    db_session.add(Project(
        project_id=uuid.uuid4(), project_no=f"P-amb2-{uuid.uuid4().hex[:6]}",
        project_name="amb2", owner_company="t", location="t",
        project_type="test", design_phase="BASIC", unit_system="SI",
        status="ACTIVE", workspace_id=ws.workspace_id))
    await db_session.commit()

    r = await strict_client.get(
        f"/api/v1/workspaces/{ws.workspace_id}", headers=_tok(owner))
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "WORKSPACE_PROJECT_AMBIGUOUS", r.text


async def test_creating_a_project_binds_the_workspace_to_it(
    strict_client, db_session
):
    """⚠️⚠️ **P0 的根因钉子**：**建项目的人**才把「工作区 ↔ 项目」绑起来。

    ⇒ ⇒ 此前 `POST /projects` 只写 `Project(workspace_id=...)` ⇒ ⇒
    ⇒ ⇒ `workspaces.project_id` **生产路径从来不写** ⇒ ⇒ 守卫的 FORMAL 分支
    ⇒ ⇒ **在生产上永远走不到**。

    ⇒ ⇒ 这条测试**走真实端点** ⇒ ⇒ 不靠夹具凑形状。
    """
    from sqlalchemy import select

    from app.models.project import Workspace as WsModel

    admin = _tok(uuid.uuid4(), "SYSTEM_ADMIN")
    owner = uuid.uuid4()
    ws = await _mk_ws(db_session, owner_id=owner)
    assert ws.project_id is None, "建项目之前，工作区本来就没有项目"

    r = await strict_client.post(
        "/api/v1/projects",
        json={
            "project_no": f"P-{uuid.uuid4().hex[:8]}",
            "project_name": "绑定测试",
            "owner_company": "PCS",
            "location": "惠州",
            "project_type": "PETROLEUM",
            "design_phase": "EXECUTIVE_DESIGN",
            "unit_system": "SI",
            "workspace_id": str(ws.workspace_id),
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    project_id = uuid.UUID(r.json()["project_id"])

    row = (
        await db_session.execute(
            select(WsModel).where(WsModel.workspace_id == ws.workspace_id)
        )
    ).scalar_one()
    # ⚠️ 端点用的是**另一个 session**（请求作用域）⇒ ⇒ 本 session 的 identity map
    # 里那份是**旧值** ⇒ ⇒ 先 expire 再查（否则读到的是缓存，不是库里的）。
    await db_session.refresh(row)
    assert row.project_id == project_id, (
        "建项目后工作区没有绑定到那个项目 ⇒ ⇒ 守卫的 FORMAL 分支走不到"
    )


async def test_creating_a_second_project_in_one_workspace_is_409(
    strict_client, db_session
):
    """⚠️ **1:1 的前置**：一个工作区**只挂一个项目** ⇒ ⇒ 第二个 ⇒ ⇒ 409。

    ⇒ ⇒ 否则会造出「歧义」⇒ ⇒ 那个工作区随后所有请求都 409（fail-loud）。
    """
    admin = _tok(uuid.uuid4(), "SYSTEM_ADMIN")
    ws = await _mk_ws(db_session, owner_id=uuid.uuid4())
    payload = {
        "project_no": f"P-{uuid.uuid4().hex[:8]}",
        "project_name": "第一个",
        "owner_company": "PCS",
        "location": "惠州",
        "project_type": "PETROLEUM",
        "design_phase": "EXECUTIVE_DESIGN",
        "unit_system": "SI",
        "workspace_id": str(ws.workspace_id),
    }
    first = await strict_client.post("/api/v1/projects", json=payload, headers=admin)
    assert first.status_code == 201, first.text

    payload["project_no"] = f"P-{uuid.uuid4().hex[:8]}"
    payload["project_name"] = "第二个"
    second = await strict_client.post("/api/v1/projects", json=payload, headers=admin)
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "WORKSPACE_ALREADY_HAS_PROJECT", second.text
