"""CIA 哈希判定分流 + manual-adjust 的端到端测试 —— P9A-4 D3（P9A-CIA-001/002）。

端点：

- ``POST /api/v1/change-impact/{record_type}/{record_id}/confirm`` —— 哈希判定分流
- ``POST /api/v1/change-impact/{record_type}/{record_id}/manual-adjust`` —— 人工判定

⚠️ `confirm` 与**既有的** `confirm-recalc` 是**两个端点**（语义不同，见模块
docstring）—— 本文件有一例专门钉住这件事。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.calc import PipingResult
from app.models.system import AuditLog

pytestmark = pytest.mark.asyncio


def _auth_headers(user_id: uuid.UUID, role: str = "CHECKER") -> dict[str, str]:
    token = create_access_token(
        subject="test-change-impact-confirm",
        role=role,
        extra={"user_id": str(user_id)},
    )
    return {"Authorization": f"Bearer {token}"}


def _make_pipe(**overrides) -> PipingResult:
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


async def _stale_pipe_with_lineage(db_session, *, baseline_hash: str) -> PipingResult:
    """造一条 STALE 记录 + 一条血缘（基线 = baseline_hash）。"""
    from app.services.lineage import LineageTracker, _compute_hash

    pipe = _make_pipe(sign_status="STALE", record_hash=baseline_hash)
    db_session.add(pipe)
    await db_session.commit()
    await db_session.refresh(pipe)

    tracker = LineageTracker(db_session)
    await tracker.track(
        record=pipe,
        source="CALC",
        change_diff={
            "hash": _compute_hash(pipe),
            "record_hash": baseline_hash,
            "formula_version": "test",
        },
    )
    await db_session.commit()
    return pipe


# ---------------------------------------------------------------------------
# 端点分离
# ---------------------------------------------------------------------------


async def test_confirm_and_confirm_recalc_are_separate_endpoints(client, user_id):
    """⚠️ `confirm` 是**新端点**，`confirm-recalc` 是 P1 已有的**传播触发器**。

    两者语义不同：前者按哈希分流（本次判定），后者无条件跑传播。
    """
    r1 = await client.post(
        f"/api/v1/change-impact/PipingResult/{uuid.uuid4()}/confirm-recalc",
        headers=_auth_headers(user_id),
    )
    r2 = await client.post(
        f"/api/v1/change-impact/PipingResult/{uuid.uuid4()}/confirm",
        headers=_auth_headers(user_id),
    )
    assert r1.status_code == 200
    assert r2.status_code in (404, 409)  # 记录不存在 ⇒ 404；不在 STALE ⇒ 409
    # 两个端点的响应体形状不同 ⇒ 不是同一个端点的两个别名
    assert "marked_stale" in r1.json()
    assert "decision" not in r1.json()


# ---------------------------------------------------------------------------
# P9A-CIA-001：哈希判定分流
# ---------------------------------------------------------------------------


async def test_unchanged_result_returns_no_change_without_credentials(
    client, db_session, user_id
):
    """结果不变 ⇒ `STALE_RESOLVED_NO_CHANGE`，**免凭证**（不必重新签署）。"""
    pipe = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")
    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm",
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["decision"] == "NO_CHANGE"
    assert data["sign_status"] == "CHECKED"
    assert data["requires_re_approval"] is False
    assert data["basis"] == "record_hash"
    assert data["stale_resolution_path"] == "cia_confirm_no_change"

    await db_session.refresh(pipe)
    assert pipe.sign_status.value == "CHECKED"
    assert pipe.stale_resolution_path == "cia_confirm_no_change"

    actions = (
        await db_session.execute(select(AuditLog.action))
    ).scalars().all()
    assert "STALE_RESOLVED_NO_CHANGE" in actions


async def test_changed_result_requires_change_pending_credentials(
    client, db_session, user_id
):
    """结果变化 ⇒ 进 CHANGE_PENDING ⇒ **要求重新签署**。"""
    pipe = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")
    # 记录被改过（hash 变了）⇒ 与基线不符
    pipe.record_hash = "ffffffffffffffff"
    await db_session.commit()

    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm",
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["decision"] == "CHANGED"
    assert data["sign_status"] == "CHANGE_PENDING"
    assert data["requires_re_approval"] is True
    assert data["stale_resolution_path"] == "cia_confirm_changed"


async def test_confirm_reuses_cia_engine_hash_comparison(
    client, db_session, user_id
):
    """判定依据与 CIA 引擎同源（血缘里的基线 hash），**不另造概念**。

    ⚠️ 血缘里**没有**可比基线 ⇒ 判「CHANGED」（保守：没有基线就无从判定
    「不变」，而「不变」是免凭证的那条 ⇒ 宁可多要一次签署）。
    """
    from app.services.lineage import LineageTracker

    pipe = _make_pipe(sign_status="STALE", record_hash="a1b2c3d4e5f60718")
    db_session.add(pipe)
    await db_session.commit()
    await db_session.refresh(pipe)
    # 血缘里只有 change_summary，没有 hash 基线
    await LineageTracker(db_session).track(
        record=pipe, source="CIA", change_summary="no baseline"
    )
    await db_session.commit()

    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm",
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["basis"] == "no_baseline"
    assert data["decision"] == "CHANGED"


async def test_confirm_on_a_non_stale_record_is_409(client, db_session, user_id):
    """不在 STALE 态 ⇒ 409（不是「静默通过」）。"""
    pipe = _make_pipe(sign_status="CHECKED", record_hash="a1b2c3d4e5f60718")
    db_session.add(pipe)
    await db_session.commit()
    await db_session.refresh(pipe)
    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/confirm",
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 409, f"got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# P9A-CIA-002：manual-adjust
# ---------------------------------------------------------------------------


async def test_manual_adjust_requires_permission_and_writes_audit(
    client, db_session, user_id
):
    """人工判定 ⇒ **限权**（无权的角色被拒）+ **写审计**（含 reason）。"""
    pipe = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")

    # DESIGNER 无权做 RESOLVE_STALE_NO_CHANGE（限权由状态机把关）
    r_denied = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/manual-adjust",
        json={"decision": "NO_CHANGE", "reason": "人工核对：结果未变"},
        headers=_auth_headers(user_id, role="DESIGNER"),
    )
    assert r_denied.status_code == 403, f"got {r_denied.status_code}: {r_denied.text}"

    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/manual-adjust",
        json={"decision": "NO_CHANGE", "reason": "人工核对：结果未变"},
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    data = r.json()
    assert data["decision"] == "NO_CHANGE"
    assert data["basis"] == "manual"
    assert data["stale_resolution_path"] == "manual_adjust_no_change"

    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "STALE_RESOLVED_NO_CHANGE",
                AuditLog.resource_id == str(pipe.pipe_id),
            )
        )
    ).scalars().all()
    assert rows, "人工判定没写审计"
    assert "人工核对" in str(rows[-1].detail_json)


async def test_manual_adjust_requires_a_reason(client, db_session, user_id):
    """人工判定**必须给依据**（reason 必填）⇒ 空 reason ⇒ 422。"""
    pipe = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")
    r = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe.pipe_id}/manual-adjust",
        json={"decision": "NO_CHANGE", "reason": ""},
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


async def test_stale_resolution_path_is_recorded_on_both_paths(
    client, db_session, user_id
):
    """两条路径都要落 `stale_resolution_path`（mixins.py 有这一列）。"""
    pipe1 = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")
    r1 = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe1.pipe_id}/confirm",
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r1.status_code == 200
    await db_session.refresh(pipe1)
    assert pipe1.stale_resolution_path == "cia_confirm_no_change"

    pipe2 = await _stale_pipe_with_lineage(db_session, baseline_hash="a1b2c3d4e5f60718")
    r2 = await client.post(
        f"/api/v1/change-impact/PipingResult/{pipe2.pipe_id}/manual-adjust",
        json={"decision": "CHANGED", "reason": "人工核对：结果已变"},
        headers=_auth_headers(user_id, role="CHECKER"),
    )
    assert r2.status_code == 200, f"got {r2.status_code}: {r2.text}"
    await db_session.refresh(pipe2)
    assert pipe2.stale_resolution_path == "manual_adjust_changed"
