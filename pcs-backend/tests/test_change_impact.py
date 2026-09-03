"""Change Impact API 端到端测试（Sprint 3）。

POST /change-impact/{record_type}/{record_id}/confirm-recalc
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


# === confirm-recalc ===

async def test_confirm_recalc_no_lineage(client):
    """无血缘时：scan=0 + propagation=0 + lineage=null。"""
    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{uuid.uuid4()}/confirm-recalc"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["record_type"] == "PipingResult"
    assert body["marked_stale"] == 0
    assert body["propagated"] == 0
    assert body["equipment_affected"] == 0
    assert body["latest_lineage"] is None


async def test_confirm_recalc_unsupported_type(client):
    """非 PipingResult 类型：返回 note。"""
    r = await client.post(
        f"/api/v1/change-impact/FlashResult/{uuid.uuid4()}/confirm-recalc"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["record_type"] == "FlashResult"
    assert body["marked_stale"] == 0
    assert "not in CIA scope" in body["note"]


async def test_confirm_recalc_with_lineage_no_mismatch(client, db_session):
    """有血缘且 hash 一致：scan=0。"""
    pipe = _make_pipe()
    await _flush_full(db_session, pipe)

    # 通过 lineage_ctx 写一条血缘（hash 与当前一致）
    from app.services.lineage import LineageTracker, _compute_hash

    current = _compute_hash(pipe)
    tracker = LineageTracker(db_session)
    await tracker.track(
        record=pipe, source="SEED", change_diff={"hash": current}
    )
    await db_session.commit()

    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm-recalc"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["marked_stale"] == 0
    assert body["propagated"] == 0
    assert body["latest_lineage"] is not None
    assert body["latest_lineage"]["source"] == "SEED"


async def test_confirm_recalc_hash_mismatch_marks_stale(client, db_session):
    """hash 写错时：scan 检测出 mismatch 并标 STALE。"""
    from app.models.enums import RecordSignStatus9
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    pipe.sign_status = RecordSignStatus9.CHECKED
    await db_session.flush()
    await db_session.refresh(pipe)

    tracker = LineageTracker(db_session)
    await tracker.track(
        record=pipe, source="SEED", change_diff={"hash": "stale_xxx"}
    )
    pipe.record_hash = "different"
    await db_session.commit()

    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm-recalc"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["marked_stale"] == 1


async def test_confirm_recalc_response_envelope(client):
    """返回字段完整性。"""
    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{uuid.uuid4()}/confirm-recalc"
    )
    body = r.json()
    for k in (
        "record_type",
        "record_id",
        "marked_stale",
        "propagated",
        "equipment_affected",
        "latest_lineage",
    ):
        assert k in body, f"missing {k}"