"""物流面**项目守卫** —— P9B-4 紧急批次 T2（10 个端点）。

## 这个文件在钉什么

2026-11-04 实测：用户只有项目 A 的权限、物流在项目 B 时 ⇒
`GET /streams/{B}` 读到**完整详情**、`POST /streams/{B}/submit` 状态**真的变成
IN_APPROVAL** ⇒ 越权是真的。

本文件给 10 个物流读/写端点钉上「跨项目一律 404」。

## ⚠️ 三个关键约束（每个都对应一类真实缺陷）

1. **「不存在」与「存在但跨项目」必须**完全同形**
   —— 都是 404 + **逐字相同**的 `code`/`message`。
   否则攻击者能靠响应差异**枚举出某个 UUID 是否存在**。

2. **守卫用 `strict_client`**
   —— 默认的 `client` fixture 把项目守卫 mock 成永远 True ⇒ 在它上面测
   「越权被拒」是**空断言**。

3. **种子数据用 ORM 直造，不用 `client` 建**
   —— `client` 的 monkeypatch 是**函数级**的 ⇒ 同一个测试里既请求 `client`
   又请求 `strict_client` ⇒ 守卫被 bypass ⇒ **假绿**。
   ⇒ 本文件**从不**在同一个测试里同时请求两者。

## 正向测试同样重要

只有 404 测试的话，一个「永远 404」的守卫也能让它们全绿 ⇒ 每个端点都有
「自己项目内**照常工作**」的对照。
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, StreamStatePoint, Workspace

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="guard-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    """`guard-designer` 派生 UUID（与 `current_actor` 一致：uuid5(DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, "guard-designer")


@pytest.fixture
def controller_headers() -> dict[str, str]:
    """PROCESS_CONTROLLER 身份 —— `approve` / `reject` 端点只放行它。"""
    token = create_access_token(subject="guard-controller", role="PROCESS_CONTROLLER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def controller_user_id() -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "guard-controller")


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="测试项目",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.commit()
        await db.refresh(proj)
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession):
    """物流工厂（ORM 直造 ⇒ 不经过任何端点 ⇒ 不受守卫影响）。"""

    async def _make(
        project: Project,
        *,
        name: str | None = None,
        stream_id: uuid.UUID | None = None,
    ) -> Stream:
        stream = Stream(
            stream_id=stream_id or uuid.uuid4(),
            project_id=project.project_id,
            workspace_id=project.workspace_id,
            stream_name=name or f"S-{uuid.uuid4().hex[:6]}",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
            sign_status=StreamSignStatus.DRAFT,
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


@pytest_asyncio.fixture
async def make_state_point(db: AsyncSession):
    """状态点工厂（ORM 直造）。"""

    async def _make(
        stream: Stream,
        *,
        state_point_id: uuid.UUID | None = None,
    ) -> StreamStatePoint:
        sp = StreamStatePoint(
            state_point_id=state_point_id or uuid.uuid4(),
            stream_id=stream.stream_id,
            state_label=f"L-{uuid.uuid4().hex[:6]}",
            case_type="NORMAL",
            temp=25.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
            composition_json={},
            source_type="MANUAL_ENTRY",
        )
        db.add(sp)
        await db.commit()
        await db.refresh(sp)
        return sp

    return _make


@pytest_asyncio.fixture
async def two_projects(
    make_project, grant_project, designer_user_id, controller_user_id
):
    """项目 A（**已授权**）+ 项目 B（**未授权**）。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(designer_user_id, project_a.project_id, username="guard-designer")
    await grant_project(
        controller_user_id, project_a.project_id, username="guard-controller"
    )
    return project_a, project_b


@pytest_asyncio.fixture
async def stream_in_b(make_stream, two_projects):
    """项目 B（**跨项目**）里的物流 + 它的状态点。"""
    _project_a, project_b = two_projects
    stream = await make_stream(project_b)
    return stream


# ---------------------------------------------------------------------------
# 10 个端点：跨项目一律 404
# ---------------------------------------------------------------------------


async def test_get_stream_in_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.get(
        f"/api/v1/streams/{stream_in_b.stream_id}", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_patch_stream_in_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.patch(
        f"/api/v1/streams/{stream_in_b.stream_id}",
        json={"payload": {"description": "改一下"}},
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text


async def test_delete_stream_in_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.delete(
        f"/api/v1/streams/{stream_in_b.stream_id}", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_create_state_point_in_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.post(
        f"/api/v1/streams/{stream_in_b.stream_id}/state-points",
        json={
            "state_label": "X-1",
            "case_type": "NORMAL",
            "temp": 25.0,
            "press": 200.0,
            "phase": "LIQUID",
            "mass_flow": 1000.0,
            "composition_json": {},
        },
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text


async def test_list_state_points_of_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.get(
        f"/api/v1/streams/{stream_in_b.stream_id}/state-points", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_get_state_point_of_another_project_is_404(
    strict_client, stream_in_b, make_state_point, designer_headers
):
    """状态点**没有** `project_id` ⇒ 守卫**经其 `stream_id` 解析**物流。"""
    sp = await make_state_point(stream_in_b)
    r = await strict_client.get(
        f"/api/v1/state-points/{sp.state_point_id}", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_patch_state_point_of_another_project_is_404(
    strict_client, stream_in_b, make_state_point, designer_headers
):
    sp = await make_state_point(stream_in_b)
    r = await strict_client.patch(
        f"/api/v1/state-points/{sp.state_point_id}",
        json={"state_label": "改一下"},
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text


async def test_delete_state_point_of_another_project_is_404(
    strict_client, stream_in_b, make_state_point, designer_headers
):
    sp = await make_state_point(stream_in_b)
    r = await strict_client.delete(
        f"/api/v1/state-points/{sp.state_point_id}", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_get_properties_of_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.get(
        f"/api/v1/streams/{stream_in_b.stream_id}/properties", headers=designer_headers
    )
    assert r.status_code == 404, r.text


async def test_estimate_properties_of_another_project_is_404(
    strict_client, stream_in_b, designer_headers
):
    r = await strict_client.post(
        f"/api/v1/streams/{stream_in_b.stream_id}/properties/estimate",
        json={"cas_list": ["7732-18-5"]},
        headers=designer_headers,
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 同形：「不存在」与「跨项目」必须**逐字相同**（Review Focus #1）
# ---------------------------------------------------------------------------


async def test_not_found_and_cross_project_are_indistinguishable(
    strict_client, make_stream, two_projects, designer_headers
):
    """不存在 ⇒ 404；跨项目 ⇒ 404；两条响应的 `code`/`message` **逐字相同**。

    ⚠️ **必须用同一个 uuid 测两次**（先「不存在」、再「存在但跨项目」）——
    这才是攻击者的视角：他请求的是**同一个** id ⇒ 两种情形下服务端回给他的
    东西必须**逐字一样**，否则能靠响应差异**枚举出某个 UUID 是否存在**。

    （拿两个**不同**的 uuid 比是**测不出**这件事的 —— 消息里本来就带着
    请求的 id。）
    """
    _project_a, project_b = two_projects
    sid = uuid.uuid4()

    # ① 此刻这条物流**还不存在**
    r_missing = await strict_client.get(
        f"/api/v1/streams/{sid}", headers=designer_headers
    )

    # ② 同一个 id，现在它**存在**但在**别的项目**里
    await make_stream(project_b, stream_id=sid)
    r_forbidden = await strict_client.get(
        f"/api/v1/streams/{sid}", headers=designer_headers
    )

    assert r_missing.status_code == r_forbidden.status_code == 404
    assert r_missing.json()["code"] == r_forbidden.json()["code"]
    assert r_missing.json()["message"] == r_forbidden.json()["message"]


async def test_state_point_not_found_and_cross_project_are_indistinguishable(
    strict_client, make_stream, make_state_point, two_projects, designer_headers
):
    """状态点侧同理（同形 ⇒ 「存在但不是我的」与「不存在」无法区分）。"""
    _project_a, project_b = two_projects
    stream = await make_stream(project_b)
    spid = uuid.uuid4()

    r_missing = await strict_client.get(
        f"/api/v1/state-points/{spid}", headers=designer_headers
    )

    await make_state_point(stream, state_point_id=spid)
    r_forbidden = await strict_client.get(
        f"/api/v1/state-points/{spid}", headers=designer_headers
    )

    assert r_missing.status_code == r_forbidden.status_code == 404
    assert r_missing.json()["code"] == r_forbidden.json()["code"]
    assert r_missing.json()["message"] == r_forbidden.json()["message"]


# ---------------------------------------------------------------------------
# 正向：自己项目内的物流**照常工作**（守卫不能把正常路径也堵死）
# ---------------------------------------------------------------------------


async def test_own_project_stream_is_fully_readable(
    strict_client, make_stream, two_projects, designer_headers
):
    """已授权的项目里 ⇒ 物流**读得到**（否则「永远 404」的守卫也能让 404 测试全绿）。"""
    project_a, _project_b = two_projects
    own = await make_stream(project_a)

    r = await strict_client.get(
        f"/api/v1/streams/{own.stream_id}", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["stream_id"] == str(own.stream_id)


async def test_own_project_state_point_is_fully_readable(
    strict_client, make_stream, make_state_point, two_projects, designer_headers
):
    """状态点侧同理：已授权项目里的状态点**读得到**。"""
    project_a, _project_b = two_projects
    own = await make_stream(project_a)
    sp = await make_state_point(own)

    r = await strict_client.get(
        f"/api/v1/state-points/{sp.state_point_id}", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["state_point_id"] == str(sp.state_point_id)


async def test_own_project_state_points_list_is_readable(
    strict_client, make_stream, make_state_point, two_projects, designer_headers
):
    """状态点**列表**在已授权项目里可读。"""
    project_a, _project_b = two_projects
    own = await make_stream(project_a)
    await make_state_point(own)

    r = await strict_client.get(
        f"/api/v1/streams/{own.stream_id}/state-points", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# 6 个状态转移端点（T3）：跨项目一律 404
# ---------------------------------------------------------------------------
#
# ⚠️ **每个端点用的身份不同** —— `approve` / `reject` 限 PROCESS_CONTROLLER
# （端点层的 `require_roles` 在守卫**之前** ⇒ 用错身份会拿到 403 而不是 404，
# 那是**角色**的判定，不是存在性的判定 ⇒ 不影响「可枚举」结论，但会让
# 本测试测不到守卫）。

_TRANSITION_ENDPOINTS = [
    ("/submit", "designer"),
    ("/approve", "controller"),
    ("/reject", "controller"),
    ("/initiate-change", "designer"),
    ("/pass-change", "designer"),
    ("/mark-stale", "designer"),
]


@pytest.mark.parametrize("path,who", _TRANSITION_ENDPOINTS)
async def test_state_transition_in_another_project_is_404(
    strict_client, stream_in_b, designer_headers, controller_headers, path, who
):
    """6 个状态转移端点：跨项目 ⇒ **404**（不是 200/403/422）。"""
    headers = designer_headers if who == "designer" else controller_headers
    body = {} if path == "/submit" else {"reason": "测试"}
    r = await strict_client.post(
        f"/api/v1/streams/{stream_in_b.stream_id}{path}", json=body, headers=headers
    )
    assert r.status_code == 404, r.text


async def test_cross_project_submit_leaks_no_composition_detail(
    strict_client, make_stream, two_projects, designer_headers, db_session
):
    """⚠️ **守卫必须先于组成门禁**（Review Focus #2）。

    这条物流的组成合计是 **50%**（非法）⇒ 修复前跨项目 submit 会返回
    **422「组成摩尔分率合计 50.00%」** ⇒ 那一条响应**同时**泄露了
    「这条物流存在」**和**「它的组成是多少」。

    ⇒ 修复后必须是 **404**，且响应里**不得**出现「组成」二字。
    """
    _project_a, project_b = two_projects
    stream = await make_stream(project_b)
    stream.composition_json = {"7732-18-5": 0.5}   # 合计 50% ⇒ 非法
    await db_session.commit()

    r = await strict_client.post(
        f"/api/v1/streams/{stream.stream_id}/submit", json={}, headers=designer_headers
    )
    assert r.status_code == 404, r.text
    assert "组成" not in r.text
    assert "50.00" not in r.text


async def test_cross_project_submit_does_not_change_status(
    strict_client, make_stream, two_projects, designer_headers, db_session
):
    """守卫失败 ⇒ 状态**一个字节都不能变**（不留半成品）。"""
    _project_a, project_b = two_projects
    stream = await make_stream(project_b)

    r = await strict_client.post(
        f"/api/v1/streams/{stream.stream_id}/submit", json={}, headers=designer_headers
    )
    assert r.status_code == 404, r.text

    await db_session.refresh(stream)
    assert stream.sign_status == StreamSignStatus.DRAFT


# ---------------------------------------------------------------------------
# 批量端点（T4 · TODO-118）：跨项目条目按「不存在」处理
# ---------------------------------------------------------------------------


async def test_batch_submit_skips_cross_project_stream_as_not_found(
    strict_client, make_stream, two_projects, designer_headers
):
    """跨项目的那条 ⇒ 报告为失败，且理由与「不存在」**逐字相同**；
    自己项目的那条 ⇒ **照常成功**（D2 部分成功语义不受守卫影响）。"""
    project_a, project_b = two_projects
    own = await make_stream(project_a)
    foreign = await make_stream(project_b)

    r = await strict_client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [str(own.stream_id), str(foreign.stream_id)]},
        headers=designer_headers,
    )
    assert r.status_code == 207, r.text
    body = r.json()

    assert [s["stream_id"] for s in body["succeeded"]] == [str(own.stream_id)]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["stream_id"] == str(foreign.stream_id)
    # ⚠️ 与「不存在」**同一个码** —— 不是 403、不是别的 code
    assert body["failed"][0]["reason"] == "SIM_STREAM_NOT_FOUND"


async def test_batch_submit_of_only_foreign_stream_looks_identical_to_missing(
    strict_client, make_stream, two_projects, designer_headers
):
    """⚠️ **同形**：跨项目条目与「不存在」条目 ⇒ **逐字相同**的失败项。

    两次请求用**同一个 uuid**（第一次：不存在；第二次：存在但在别的项目）
    ⇒ 攻击者看到的失败项必须一模一样 ⇒ 无法判断那个 UUID 是否存在。
    """
    _project_a, project_b = two_projects
    sid = uuid.uuid4()

    # ① 此刻这条物流**还不存在**
    r_missing = await strict_client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [str(sid)]},
        headers=designer_headers,
    )

    # ② 同一个 id，现在它**存在**但在**别的项目**里
    await make_stream(project_b, stream_id=sid)
    r_forbidden = await strict_client.post(
        "/api/v1/streams/batch-submit",
        json={"stream_ids": [str(sid)]},
        headers=designer_headers,
    )

    assert r_missing.status_code == r_forbidden.status_code == 207
    failed_missing = r_missing.json()["failed"]
    failed_forbidden = r_forbidden.json()["failed"]
    assert len(failed_missing) == len(failed_forbidden) == 1
    assert failed_missing[0]["reason"] == failed_forbidden[0]["reason"]
    assert failed_missing[0]["detail"] == failed_forbidden[0]["detail"]
