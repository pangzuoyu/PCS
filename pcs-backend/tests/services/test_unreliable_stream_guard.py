"""P3.x SIM-39 / TODO-037: 不可靠物流下游计算硬拒绝守卫。

背景（plan PCS-P3.2-SIM §self-review + 用户 2026-09-08 裁决）：
- P3.2 SIM-10 仅标记 `streams.is_unreliable=True`（NOT_CONVERGED/ABORTED
  单元产品）；不阻止使用
- SIM-39（合入）：实现可复用守卫 UnreliableStreamGuard.check ——
  P4 工艺计算入口（POST /api/v1/calculate/...）调用；
  任意输入流 unreliable=True → 422 STREAM_UNRELIABLE_BLOCKED + 流名清单

契约（TODO-037 定义）：
- 422 code=STREAM_UNRELIABLE_BLOCKED
- 错误消息列出全部不可靠流名（sorted）
- 空输入集直通；全部可靠直通
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.models.project import Stream
from app.services.exceptions import PcsError
from app.services.unreliable_stream_guard import UnreliableStreamGuard


class _FakeResult:
    """select(...).scalars().all() 占位。"""

    def __init__(self, names: list[str]) -> None:
        self._names = names

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[str]:
        return self._names


class _FakeSession:
    """最小 AsyncSession 占位：execute 返回罐头不可靠流名。"""

    def __init__(self, unreliable_names: list[str]) -> None:
        self._names = unreliable_names

    async def execute(self, stmt: Any) -> _FakeResult:
        return _FakeResult(list(self._names))


# ============================================================================
# 直通场景
# ============================================================================


@pytest.mark.asyncio
async def test_empty_input_set_passes():
    """空输入集 → 直通（checked=0）。"""
    db = _FakeSession(unreliable_names=[])
    result = await UnreliableStreamGuard.check(db, [])
    assert result == {"checked": 0, "unreliable_names": []}


@pytest.mark.asyncio
async def test_all_reliable_streams_pass():
    """全部可靠流 → 直通。"""
    db = _FakeSession(unreliable_names=[])
    ids = [uuid.uuid4() for _ in range(3)]
    result = await UnreliableStreamGuard.check(db, ids)
    assert result["checked"] == 3
    assert result["unreliable_names"] == []


@pytest.mark.asyncio
async def test_duplicate_ids_counted_once():
    """重复 stream_id 去重后计数。"""
    db = _FakeSession(unreliable_names=[])
    sid = uuid.uuid4()
    result = await UnreliableStreamGuard.check(db, [sid, sid, sid])
    assert result["checked"] == 1


# ============================================================================
# 硬拒绝场景（TODO-037 核心）
# ============================================================================


@pytest.mark.asyncio
async def test_any_unreliable_raises_422_with_code():
    """任意输入流 unreliable=True → 422 STREAM_UNRELIABLE_BLOCKED。"""
    db = _FakeSession(unreliable_names=["1NAPHTHA"])
    with pytest.raises(PcsError) as exc_info:
        await UnreliableStreamGuard.check(db, [uuid.uuid4()])
    assert exc_info.value.status == 422
    assert exc_info.value.code == "STREAM_UNRELIABLE_BLOCKED"


@pytest.mark.asyncio
async def test_error_message_lists_unreliable_stream_names():
    """错误消息列出全部不可靠流名（sorted）。"""
    db = _FakeSession(unreliable_names=["1LCO", "1NAPHTHA", "1SLURRYR"])
    with pytest.raises(PcsError) as exc_info:
        await UnreliableStreamGuard.check(db, [uuid.uuid4() for _ in range(3)])
    msg = str(exc_info.value)
    assert "1NAPHTHA" in msg
    assert "1LCO" in msg
    assert "1SLURRYR" in msg


# ============================================================================
# Stream 模型契约（is_unreliable 字段存在性）
# ============================================================================


def test_stream_model_has_is_unreliable_column():
    """Stream.is_unreliable 列存在（SIM-10 标记基础，本守卫依赖）。"""
    cols = Stream.__table__.columns
    assert "is_unreliable" in cols
