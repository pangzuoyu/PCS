"""物流列表的四项筛选（SPEC §7.7.1 · P9B-3 · 评审 I-4）。

## 为什么这个文件存在

SPEC §7.7.1：物流列表的筛选有**工况 / 相态 / 状态 / 来源**四项，**四项均随选择
重新请求后端，后端按 AND 组合过滤**。

⚠️ 前端（T6）只断言「请求**带了** query 参数」⇒ **后端是否真的按它筛**没人管
⇒ 后端把 `?phase=` 的过滤条件写错一行 ⇒ 前端选了相态、请求也带上了参数、
后端**静默忽略** ⇒ **所有测试仍然绿**。

⇒ 本文件把**后端**的筛选行为钉住（`case_type` 另有既有测试；`source` 在
`test_stream_source.py`；这里补 `phase` 与 `sign_status`）。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def make_project(db_session: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db_session.add(ws)
        await db_session.flush()
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
        db_session.add(proj)
        await db_session.commit()
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


def _payload(**kw) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        stream_name="S-101",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"7732-18-5": 1.0},
    )
    base.update(kw)
    return base


async def _create(client, proj, headers, **kw) -> dict[str, Any]:
    resp = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _payload(**kw)},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_list_filter_by_phase(client, make_project, designer_headers):
    """`?phase=VAPOR` ⇒ 只返回相态匹配的（不是「带了参数但没筛」）。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-LIQ", phase="LIQUID")
    await _create(client, proj, designer_headers, stream_name="S-VAP", phase="VAPOR")

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?phase=VAPOR",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert [i["stream_name"] for i in resp.json()] == ["S-VAP"]


async def test_list_filter_by_sign_status(
    client, db_session, make_project, designer_headers
):
    """`?sign_status=CHECKED` ⇒ 只返回状态匹配的（不是「带了参数但没筛」）。"""
    from sqlalchemy import update

    from app.models.enums import StreamSignStatus
    from app.models.project import Stream

    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-DRAFT")
    checked = await _create(client, proj, designer_headers, stream_name="S-CHECKED")

    # 直连 DB 改状态（本用例只关心**筛选**行为，不关心状态机怎么推进）
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == uuid.UUID(checked["stream_id"]))
        .values(sign_status=StreamSignStatus.CHECKED)
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?sign_status=CHECKED",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert [i["stream_name"] for i in resp.json()] == ["S-CHECKED"]


async def test_list_filters_are_combined_with_and(
    client, make_project, designer_headers
):
    """⚠️ 四项筛选按 **AND** 组合（SPEC §7.7.1）—— 不是「任一命中」。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-1", phase="LIQUID")
    await _create(client, proj, designer_headers, stream_name="S-2", phase="VAPOR")

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?phase=LIQUID&case_type=NORMAL",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert [i["stream_name"] for i in resp.json()] == ["S-1"]

    # 相态命中但工况不命中 ⇒ 空（AND ⇒ 一个都不返回）
    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?phase=LIQUID&case_type=TURN_DOWN",
        headers=designer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
