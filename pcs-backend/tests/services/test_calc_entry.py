"""P4-0-3 计算入口守卫接线（fake session，无 DB）。

三步顺序：
1. 物流存在（Stream SELECT WHERE stream_id IN）— 任一不存在 → StreamNotFoundError
2. CHECKED 校验（sign_status == CHECKED）— 否则 → StreamNotCheckedError（403）
3. 不可靠流守卫（UnreliableStreamGuard.check）— 命中 → StreamUnreliableError（422）

契约与既有对齐：
- StreamNotFoundError: 404 SIM_STREAM_NOT_FOUND（与 stream_service.get 一致）
- StreamNotCheckedError: 403 STREAM_NOT_CHECKED（新代码，P4-0-3 引入）
- StreamUnreliableError: 422 STREAM_UNRELIABLE_BLOCKED（与 unreliable_stream_guard 一致）
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.models.enums import StreamSignStatus


class _FakeStream:
    """Stream 行占位（fake session 无 ORM 列映射）。"""

    def __init__(
        self,
        stream_id: uuid.UUID,
        stream_name: str = "S-001",
        sign_status: StreamSignStatus = StreamSignStatus.CHECKED,
        is_unreliable: bool = False,
    ) -> None:
        self.stream_id = stream_id
        self.stream_name = stream_name
        self.sign_status = sign_status
        self.is_unreliable = is_unreliable


class _FakeResult:
    """select(...).scalars().all() 占位。"""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list:
        return list(self._rows)


class _FakeSession:
    """最小 AsyncSession 占位：两个 SELECT 顺序响应。

    第一次 execute：返回传入的全部 streams（模拟 SELECT Stream WHERE stream_id IN）。
    第二次 execute：返回 unreliable 流名清单（模拟 UnreliableStreamGuard 的查询）。

    顺序契约：check_calc_inputs 先 existence+sign_status 查，再 UnreliableStreamGuard。
    """

    def __init__(self, streams: list[_FakeStream]) -> None:
        self._streams = list(streams)
        self._call_count = 0

    async def execute(self, stmt: Any) -> _FakeResult:
        self._call_count += 1
        if self._call_count == 1:
            # existence + sign_status 查询：返回 fake session 中所有流
            return _FakeResult(self._streams)
        # UnreliableStreamGuard 查询：返回 unreliable 流名
        return _FakeResult(
            [s.stream_name for s in self._streams if s.is_unreliable]
        )


# ============================================================================
# 1. happy path：全 CHECKED + 全可靠
# ============================================================================


@pytest.mark.asyncio
async def test_three_checked_reliable_streams_pass() -> None:
    """3 条 stream 全 CHECKED + 不可靠守卫全通过 → 不抛。"""
    from app.services.calc_entry import check_calc_inputs

    ids = [uuid.uuid4() for _ in range(3)]
    streams = [
        _FakeStream(sid, stream_name=f"S-{i}", sign_status=StreamSignStatus.CHECKED)
        for i, sid in enumerate(ids)
    ]
    db = _FakeSession(streams)
    # 不抛即通过
    await check_calc_inputs(db, ids)


# ============================================================================
# 2. 物流不存在 → StreamNotFoundError（404 SIM_STREAM_NOT_FOUND）
# ============================================================================


@pytest.mark.asyncio
async def test_missing_stream_raises_not_found() -> None:
    """1 个 ID 不在库 → raise StreamNotFoundError（404 SIM_STREAM_NOT_FOUND）。"""
    from app.services.calc_entry import StreamNotFoundError, check_calc_inputs

    present_id = uuid.uuid4()
    missing_id = uuid.uuid4()
    streams = [_FakeStream(present_id)]
    db = _FakeSession(streams)
    with pytest.raises(StreamNotFoundError) as exc_info:
        await check_calc_inputs(db, [present_id, missing_id])
    assert exc_info.value.status == 404
    assert exc_info.value.code == "SIM_STREAM_NOT_FOUND"
    # 错误消息含具体缺失 ID
    assert str(missing_id) in str(exc_info.value)


# ============================================================================
# 3. 物流非 CHECKED → StreamNotCheckedError（403 STREAM_NOT_CHECKED）
# ============================================================================


@pytest.mark.asyncio
async def test_draft_stream_raises_not_checked() -> None:
    """1 条 DRAFT → raise StreamNotCheckedError（403 STREAM_NOT_CHECKED）。"""
    from app.services.calc_entry import StreamNotCheckedError, check_calc_inputs

    sid = uuid.uuid4()
    streams = [_FakeStream(sid, stream_name="S-DRAFT", sign_status=StreamSignStatus.DRAFT)]
    db = _FakeSession(streams)
    with pytest.raises(StreamNotCheckedError) as exc_info:
        await check_calc_inputs(db, [sid])
    assert exc_info.value.status == 403
    assert exc_info.value.code == "STREAM_NOT_CHECKED"
    # 错误消息含流名与状态
    msg = str(exc_info.value)
    assert "S-DRAFT" in msg
    assert "DRAFT" in msg


# ============================================================================
# 4. 物流不可靠 → StreamUnreliableError（422 STREAM_UNRELIABLE_BLOCKED）
# ============================================================================


@pytest.mark.asyncio
async def test_unreliable_stream_raises_blocked() -> None:
    """1 条 is_unreliable=True → raise StreamUnreliableError（422）。"""
    from app.services.calc_entry import StreamUnreliableError, check_calc_inputs

    sid = uuid.uuid4()
    streams = [
        _FakeStream(sid, stream_name="1NAPHTHA", is_unreliable=True),
    ]
    db = _FakeSession(streams)
    with pytest.raises(StreamUnreliableError) as exc_info:
        await check_calc_inputs(db, [sid])
    assert exc_info.value.status == 422
    assert exc_info.value.code == "STREAM_UNRELIABLE_BLOCKED"


# ============================================================================
# 5. 多 stream 部分失败：顺序 exists → CHECKED → unreliable
# ============================================================================


@pytest.mark.asyncio
async def test_multiple_streams_one_missing_raises_not_found_first() -> None:
    """3 条 stream：1 条缺失 → 抛 StreamNotFoundError（顺序首位）。"""
    from app.services.calc_entry import StreamNotFoundError, check_calc_inputs

    present_a = uuid.uuid4()
    present_b = uuid.uuid4()
    missing = uuid.uuid4()
    streams = [
        _FakeStream(present_a, stream_name="A", sign_status=StreamSignStatus.CHECKED),
        _FakeStream(present_b, stream_name="B", sign_status=StreamSignStatus.CHECKED),
    ]
    db = _FakeSession(streams)
    with pytest.raises(StreamNotFoundError):
        await check_calc_inputs(db, [present_a, present_b, missing])


@pytest.mark.asyncio
async def test_multiple_streams_one_draft_raises_not_checked() -> None:
    """3 条 stream：全存在但 1 条 DRAFT → 抛 StreamNotCheckedError。"""
    from app.services.calc_entry import StreamNotCheckedError, check_calc_inputs

    sid_a = uuid.uuid4()
    sid_b = uuid.uuid4()
    sid_draft = uuid.uuid4()
    streams = [
        _FakeStream(sid_a, stream_name="A", sign_status=StreamSignStatus.CHECKED),
        _FakeStream(sid_b, stream_name="B", sign_status=StreamSignStatus.CHECKED),
        _FakeStream(sid_draft, stream_name="D", sign_status=StreamSignStatus.DRAFT),
    ]
    db = _FakeSession(streams)
    with pytest.raises(StreamNotCheckedError):
        await check_calc_inputs(db, [sid_a, sid_b, sid_draft])


@pytest.mark.asyncio
async def test_multiple_streams_one_unreliable_raises_blocked() -> None:
    """3 条 stream：全 CHECKED 但 1 条 unreliable → 抛 StreamUnreliableError。"""
    from app.services.calc_entry import StreamUnreliableError, check_calc_inputs

    sid_a = uuid.uuid4()
    sid_b = uuid.uuid4()
    sid_bad = uuid.uuid4()
    streams = [
        _FakeStream(sid_a, stream_name="A", sign_status=StreamSignStatus.CHECKED),
        _FakeStream(sid_b, stream_name="B", sign_status=StreamSignStatus.CHECKED),
        _FakeStream(
            sid_bad,
            stream_name="1NAPHTHA",
            sign_status=StreamSignStatus.CHECKED,
            is_unreliable=True,
        ),
    ]
    db = _FakeSession(streams)
    with pytest.raises(StreamUnreliableError):
        await check_calc_inputs(db, [sid_a, sid_b, sid_bad])


# ============================================================================
# 6. 空 stream_ids：直通（与 UnreliableStreamGuard.check 空集约定一致）
# ============================================================================


@pytest.mark.asyncio
async def test_empty_stream_ids_pass_through() -> None:
    """stream_ids=[] → 不抛（无流可校验；与 UnreliableStreamGuard.check 直通约定一致）。"""
    from app.services.calc_entry import check_calc_inputs

    db = _FakeSession([])
    # 不抛即通过
    await check_calc_inputs(db, [])
    # 空集不应触发任何查询
    assert db._call_count == 0