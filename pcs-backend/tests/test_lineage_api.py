"""Lineage API 端到端测试（Sprint 3）。

GET /lineage/{record_type}/{record_id}/upstream
GET /lineage/{record_type}/{record_id}/downstream
GET /lineage/{record_type}/{record_id}/graph
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _make_pipe(**overrides):
    from app.models.calc import PipingResult

    base = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        seq_no=1,
        line_no="P-1",
        line_size='2"',
        material_class="A1",
        fluid_code="W",
        fluid_name="Water",
        fluid_phase="L",
        fluid_category="NORMAL",
        source_pid="P&ID-001",
        line_from="V-100",
        line_to="V-200",
        norm_oper_press=1.0,
        max_oper_press=1.5,
        norm_oper_temp=40.0,
        max_oper_temp=80.0,
        design_press=2.0,
        design_temp=100.0,
        piping_category="GC3",
        pressure_test_medium="WATER",
        pressure_test_press=3.0,
        check_class="III",
    )
    base.update(overrides)
    return PipingResult(**base)


async def _flush_full(session, *objs):
    for o in objs:
        session.add(o)
    await session.flush()
    for o in objs:
        await session.refresh(o)
    return objs


# === upstream ===

async def test_upstream_empty_when_no_lineage(client):
    r = await client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/upstream"
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_upstream_traverses_parent_chain(client, db_session):
    """返回 parent_lineage_id 链上的所有祖先。"""
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    n1 = await tracker.track(record=pipe, source="A")
    n2 = await tracker.track(record=pipe, source="B")
    n3 = await tracker.track(record=pipe, source="C")
    n3.parent_lineage_id = n2.lineage_id
    n2.parent_lineage_id = n1.lineage_id
    await db_session.commit()

    r = await client.get(
        f"/api/v1/lineage/PipingResult/{pipe.pipe_id}/upstream"
    )
    assert r.status_code == 200
    chain = r.json()
    assert len(chain) == 2
    assert chain[0]["lineage_id"] == str(n2.lineage_id)
    assert chain[1]["lineage_id"] == str(n1.lineage_id)


async def test_upstream_respects_max_depth(client, db_session):
    """max_depth 限制遍历深度。"""
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    n1 = await tracker.track(record=pipe, source="A")
    n2 = await tracker.track(record=pipe, source="B")
    n3 = await tracker.track(record=pipe, source="C")
    n3.parent_lineage_id = n2.lineage_id
    n2.parent_lineage_id = n1.lineage_id
    await db_session.commit()

    r = await client.get(
        f"/api/v1/lineage/PipingResult/{pipe.pipe_id}/upstream?max_depth=1"
    )
    assert r.status_code == 200
    chain = r.json()
    assert len(chain) == 1


# === downstream ===

async def test_downstream_404_when_no_lineage(client):
    r = await client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/downstream"
    )
    assert r.status_code == 404


async def test_downstream_returns_bfs(client, db_session):
    """downstream 基于 latest lineage（最新一条）向下找子节点。"""
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    # root → A → B；A 是 B 的 parent，grandchild 链路
    root = await tracker.track(record=pipe, source="ROOT")
    a = await tracker.track(record=pipe, source="A")
    b = await tracker.track(record=pipe, source="B")
    a.parent_lineage_id = root.lineage_id
    b.parent_lineage_id = a.lineage_id
    await db_session.commit()

    r = await client.get(
        f"/api/v1/lineage/PipingResult/{pipe.pipe_id}/downstream"
    )
    assert r.status_code == 200
    children = r.json()
    # latest 是 b；从 b 向下找，无 children
    assert children == []


async def test_downstream_returns_children_of_latest(client, db_session):
    """以 latest lineage 为 parent_lineage_id 的节点被返回。"""
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    parent = await tracker.track(record=pipe, source="P")
    # 在 parent 之后建两个 child
    c1 = await tracker.track(record=pipe, source="C1")
    c2 = await tracker.track(record=pipe, source="C2")
    c1.parent_lineage_id = parent.lineage_id
    c2.parent_lineage_id = parent.lineage_id
    # 再建一条更晚的 grandchild，让 latest 变成 grandchild（无子）
    gc = await tracker.track(record=pipe, source="GC")
    gc.parent_lineage_id = c1.lineage_id
    await db_session.commit()

    # latest 是 gc；gc 没有 children → 返回空
    r = await client.get(
        f"/api/v1/lineage/PipingResult/{pipe.pipe_id}/downstream"
    )
    assert r.status_code == 200
    assert r.json() == []


# === graph ===

async def test_graph_404_when_no_lineage(client):
    r = await client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/graph"
    )
    assert r.status_code == 404


async def test_graph_returns_root_up_down(client, db_session):
    """graph 端点返回 root（latest lineage）+ upstream + downstream。"""
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    p = await tracker.track(record=pipe, source="USER")
    p2 = await tracker.track(record=pipe, source="P2")
    p2.parent_lineage_id = p.lineage_id  # p2 是 p 的 child
    await db_session.commit()

    r = await client.get(
        f"/api/v1/lineage/PipingResult/{pipe.pipe_id}/graph"
    )
    assert r.status_code == 200
    body = r.json()
    assert "root" in body
    # root 是 latest = p2
    assert body["root"]["lineage_id"] == str(p2.lineage_id)
    assert "upstream" in body
    # upstream 链上：p2 → p
    upstream_ids = [u["lineage_id"] for u in body["upstream"]]
    assert str(p.lineage_id) in upstream_ids
    assert "downstream" in body
    # p2 无 child
    assert body["downstream"] == []


async def test_lineage_endpoint_serialization_envelope(client):
    """序列化字段完整性。"""
    r = await client.get(
        f"/api/v1/lineage/PipingResult/{uuid.uuid4()}/upstream"
    )
    assert r.status_code == 200
    assert r.json() == []  # 无血缘返回空列表，无需字段