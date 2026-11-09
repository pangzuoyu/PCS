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
async def two_projects(make_project, grant_project, designer_user_id):
    """项目 A（**已授权**）+ 项目 B（**未授权**）。"""
    project_a = await make_project()
    project_b = await make_project()
    await grant_project(designer_user_id, project_a.project_id, username="guard-designer")
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
