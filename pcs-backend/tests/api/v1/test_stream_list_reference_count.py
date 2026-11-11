"""物流列表的「引用 📎×N」字段（P9B-4 · TODO-108）。

## 这个文件在钉什么

1. 列表响应**每行都带** `reference_count`（**必填**，默认 0）；
2. 无引用 ⇒ 0；
3. ⚠️ **N+1 守卫** —— 计数**不能**逐行查 ⇒ `reference_counts` **只被调用一次**
   （整个列表 2 条聚合查询）。

⚠️ 口径本身（什么算引用）在
`tests/services/test_stream_reference_count.py` 里钉 ⇒ 本文件只管**接线**。
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
            project_name="引用计数测试",
            owner_company="测试业主",
            location="测试地点",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db_session.add(proj)
        await db_session.commit()
        await db_session.refresh(proj)
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="ref-designer", role="DESIGNER")
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


async def test_list_streams_includes_reference_count(
    client, make_project, designer_headers
):
    """列表响应每行都带 `reference_count`。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-1")

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert "reference_count" in items[0]
    assert isinstance(items[0]["reference_count"], int)


async def test_list_streams_reference_count_is_zero_when_unreferenced(
    client, make_project, designer_headers
):
    """无引用 ⇒ 0（**不是**缺字段、也不是 null）。"""
    proj = await make_project()
    await _create(client, proj, designer_headers, stream_name="S-1")

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    items = resp.json()
    assert items[0]["reference_count"] == 0


async def test_list_streams_counts_downstream_streams(
    client, db_session, make_project, designer_headers
):
    """下游物流 ⇒ 被引用的那条计数 ≥ 1。"""
    from sqlalchemy import update

    from app.models.project import Stream

    proj = await make_project()
    upstream = await _create(client, proj, designer_headers, stream_name="S-UP")
    downstream = await _create(client, proj, designer_headers, stream_name="S-DOWN")

    # 直连 DB 建「下游」关系（API 的创建载荷里没有 upstream_stream_id）
    await db_session.execute(
        update(Stream)
        .where(Stream.stream_id == uuid.UUID(downstream["stream_id"]))
        .values(upstream_stream_id=uuid.UUID(upstream["stream_id"]))
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    items = {i["stream_name"]: i for i in resp.json()}
    assert items["S-UP"]["reference_count"] == 1
    assert items["S-DOWN"]["reference_count"] == 0


async def test_list_streams_does_not_query_per_row(
    client, monkeypatch, make_project, designer_headers
):
    """⚠️ **N+1 守卫**：列表 10 条物流 ⇒ 计数**不是** 10 次。

    ⇒ 断言 `StreamService.reference_counts` **只被调用一次**。
    """
    from app.services.stream_service import StreamService

    proj = await make_project()
    for i in range(10):
        await _create(
            client, proj, designer_headers, stream_name=f"S-{i:02d}"
        )

    calls: list[int] = []
    real = StreamService.reference_counts

    async def _spy(db, stream_ids):  # noqa: ANN001
        calls.append(len(list(stream_ids)))
        return await real(db, stream_ids)

    monkeypatch.setattr(StreamService, "reference_counts", staticmethod(_spy))

    resp = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams", headers=designer_headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 10
    # ⚠️ **一次**调用（不是 10 次）⇒ 不是 N+1
    assert len(calls) == 1, f"reference_counts 被调 {len(calls)} 次 ⇒ N+1"
    assert calls[0] == 10
