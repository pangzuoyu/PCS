"""P3.x SIM-39 / TODO-044: 状态机审计日志结构化（snapshot 链）。

背景（CLOSE-REPORT TODO-044）：
- 现状 detail={from/to/transition/reason/role}（已含转移原因与角色）
- 残余缺口：转移触发快照创建/恢复时，audit 不引用 snapshot_id ——
  审计无法回链到 record_change_snapshots 快照链

SIM-39 增量契约：
- detail 新增两键（additive，不破坏既有结构）：
  - snapshot_id: str | None（本次转移创建或恢复的快照 UUID）
  - snapshot_action: "CREATED" | "RESTORED" | None
- 创建快照转移（APPLY_CHANGE / RESOLVE_STALE_CHANGED）：CREATED + id
- 恢复快照转移（ABANDON_CHANGE / APPROVE_REVERSAL）：RESTORED + id
- 无快照转移（SUBMIT_FOR_CHECK 等）：两键均 None
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest

from app.models.deliverable import RecordChangeSnapshot
from app.models.enums import StateTransition
from app.models.project import Stream
from app.services.state_machine import StateMachineService


class _FakeStream(Stream):
    """Stream 子类 fake（mapper 检查兼容 _record_pk）。"""


class _FakeSnapshotResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _FakeSession:
    """最小 AsyncSession：add 捕获 / execute 返回罐头 ACTIVE 快照。"""

    def __init__(self, active_snapshot: RecordChangeSnapshot | None = None) -> None:
        self.added: list[Any] = []
        self.active_snapshot = active_snapshot

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any) -> _FakeSnapshotResult:
        return _FakeSnapshotResult(self.active_snapshot)

    async def flush(self) -> None:
        return None


def _make_stream(sign_status: str) -> _FakeStream:
    s = _FakeStream()
    s.stream_id = uuid.uuid4()
    s.sign_status = sign_status
    s.record_hash = "hash-1"
    s.change_pending_since = datetime(2026, 9, 1)
    return s


async def _transition_capture_detail(
    sign_status: str,
    transition: StateTransition,
    role: str = "DESIGNER",
    active_snapshot: RecordChangeSnapshot | None = None,
) -> dict:
    """跑一次转移并捕获 audit detail（monkeypatch AuditService.write）。"""
    from app.services import audit_service as audit_mod

    stream = _make_stream(sign_status)
    db = _FakeSession(active_snapshot=active_snapshot)
    captured: list[dict] = []

    async def _capture(self, *, action, resource_type, resource_id, user_id, detail):
        captured.append(detail)

    orig = audit_mod.AuditService.write
    audit_mod.AuditService.write = _capture  # type: ignore[assignment]
    try:
        await StateMachineService(db).transition(
            record=stream,
            transition=transition,
            actor_user_id=uuid.uuid4(),
            actor_role=role,
            reason="测试",
        )
    finally:
        audit_mod.AuditService.write = orig  # type: ignore[assignment]
    assert captured, "audit 未写入"
    return captured[0]


# ============================================================================
# 既有结构保留（additive 回归）
# ============================================================================


@pytest.mark.asyncio
async def test_detail_retains_core_keys():
    """detail 保留 from/to/transition/reason/role 五键（结构回归）。"""
    detail = await _transition_capture_detail(
        "DRAFT", StateTransition.SUBMIT_FOR_CHECK,
    )
    assert detail["from"] == "DRAFT"
    assert detail["to"] == "IN_APPROVAL"
    assert detail["transition"] == "SUBMIT_FOR_CHECK"
    assert detail["reason"] == "测试"
    assert detail["role"] == "DESIGNER"


# ============================================================================
# snapshot 链结构化（TODO-044 核心）
# ============================================================================


@pytest.mark.asyncio
async def test_initiate_change_audit_has_snapshot_created():
    """INITIATE_CHANGE 创建 BEFORE_CHANGE 快照 → snapshot_action=CREATED + snapshot_id。"""
    detail = await _transition_capture_detail(
        "CHECKED", StateTransition.INITIATE_CHANGE,
    )
    assert detail["snapshot_action"] == "CREATED"
    assert detail["snapshot_id"] is not None
    uuid.UUID(detail["snapshot_id"])  # 合法 UUID


@pytest.mark.asyncio
async def test_abandon_change_audit_has_snapshot_restored():
    """ABANDON_CHANGE 恢复快照 → snapshot_action=RESTORED + snapshot_id。"""
    snap = RecordChangeSnapshot(
        record_type="_FakeStream",
        record_id=uuid.uuid4(),
        record_hash="hash-1",
        data_snapshot_json={},
        snapshot_reason="BEFORE_CHANGE",
        snapshot_source="MANUAL_CHANGE",
        snapshot_status="ACTIVE",
    )
    detail = await _transition_capture_detail(
        "CHANGE_PENDING", StateTransition.ABANDON_CHANGE,
        active_snapshot=snap,
    )
    assert detail["snapshot_action"] == "RESTORED"
    assert detail["snapshot_id"] == str(snap.snapshot_id)


@pytest.mark.asyncio
async def test_no_snapshot_transition_audit_keys_none():
    """无快照转移（SUBMIT_FOR_CHECK）→ snapshot_id/snapshot_action 均 None。"""
    detail = await _transition_capture_detail(
        "DRAFT", StateTransition.SUBMIT_FOR_CHECK,
    )
    assert detail["snapshot_id"] is None
    assert detail["snapshot_action"] is None


@pytest.mark.asyncio
async def test_abandon_change_without_snapshot_action_none():
    """ABANDON_CHANGE 但无 ACTIVE 快照 → snapshot_action=None（不阻断）。"""
    detail = await _transition_capture_detail(
        "CHANGE_PENDING", StateTransition.ABANDON_CHANGE,
    )
    # _FakeSession 默认无 ACTIVE 快照
    assert detail["snapshot_action"] is None
    assert detail["snapshot_id"] is None
