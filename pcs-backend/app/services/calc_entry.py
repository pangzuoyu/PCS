"""P4-0-3 计算入口守卫接线（TODO-038）。

三步顺序硬拒绝（P4 工艺计算入口前置守卫）：
1. **物流存在**：SELECT streams WHERE stream_id IN (...) — 任一不存在
   → StreamNotFoundError（404 SIM_STREAM_NOT_FOUND，消息含具体缺失 ID）。
2. **CHECKED 校验**：每条 stream 的 sign_status == CHECKED — 否则
   → StreamNotCheckedError（403 STREAM_NOT_CHECKED，消息含流名与状态）。
3. **不可靠流守卫**：调 UnreliableStreamGuard.check（既有 SIM-39 守卫）——
   命中 → StreamUnreliableError（422 STREAM_UNRELIABLE_BLOCKED，消息含流名清单）。

空 stream_ids 直通（与 UnreliableStreamGuard.check 空集约定一致：无流可校验）。

异常类与既有契约对齐：
- StreamNotFoundError → code/status 与 StreamService.get 一致（SIM_STREAM_NOT_FOUND/404）
- StreamNotCheckedError → 新代码 STREAM_NOT_CHECKED/403（P4-0-3 引入）
- StreamUnreliableError → code/status 与 UnreliableStreamGuard.check 一致
  （STREAM_UNRELIABLE_BLOCKED/422），异常实例化时透传其 PcsError 内容
  （不重写消息/code/status，确保 422 错误响应 byte-for-byte 等价）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StreamSignStatus
from app.models.project import Stream
from app.services.exceptions import PcsError
from app.services.unreliable_stream_guard import UnreliableStreamGuard


class StreamNotFoundError(PcsError):
    """物流不存在（404 SIM_STREAM_NOT_FOUND）。契约与 StreamService.get 一致。"""

    code = "SIM_STREAM_NOT_FOUND"
    status = 404


class StreamNotCheckedError(PcsError):
    """物流未达 CHECKED 状态（403 STREAM_NOT_CHECKED，P4-0-3 引入）。"""

    code = "STREAM_NOT_CHECKED"
    status = 403


class StreamUnreliableError(PcsError):
    """输入流含不可靠流（422 STREAM_UNRELIABLE_BLOCKED）。契约与
    UnreliableStreamGuard.check 一致；异常构造时透传守卫抛出的 PcsError，
    保证 422 错误响应（code/status/message）byte-for-byte 等价。
    """

    code = "STREAM_UNRELIABLE_BLOCKED"
    status = 422


async def check_calc_inputs(
    db: AsyncSession,
    stream_ids: list[uuid.UUID],
) -> None:
    """统一入口：物流存在 → CHECKED 校验(403) → UnreliableStreamGuard.check(422)。

    P4 工艺计算入口（POST /api/v1/calculate/...）前置守卫。
    任一步失败即抛异常，由 FastAPI exception handler 翻译为 4xx 响应。

    Args:
        db: async session
        stream_ids: 计算输入流 UUID 集（重复自动去重；空集直通）

    Raises:
        StreamNotFoundError: 任一 stream_id 不存在（404 SIM_STREAM_NOT_FOUND）
        StreamNotCheckedError: 任一 stream 未达 CHECKED 状态（403 STREAM_NOT_CHECKED）
        StreamUnreliableError: 任一 stream 触发 UnreliableStreamGuard
            （422 STREAM_UNRELIABLE_BLOCKED）
    """
    # 去重 + 空集直通（与 UnreliableStreamGuard.check 空集约定一致）
    ids = list(dict.fromkeys(stream_ids))
    if not ids:
        return

    # Step 1：物流存在
    found = (
        await db.execute(select(Stream).where(Stream.stream_id.in_(ids)))
    ).scalars().all()
    if len(found) != len(ids):
        found_ids = {s.stream_id for s in found}
        missing = [sid for sid in ids if sid not in found_ids]
        raise StreamNotFoundError(
            f"物流不存在：{[str(m) for m in missing]}",
            code=StreamNotFoundError.code,
            status=StreamNotFoundError.status,
        )

    # Step 2：CHECKED 校验
    for stream in found:
        if stream.sign_status != StreamSignStatus.CHECKED:
            status_name = (
                stream.sign_status.value
                if hasattr(stream.sign_status, "value")
                else str(stream.sign_status)
            )
            raise StreamNotCheckedError(
                f"物流 {stream.stream_name} 未达 CHECKED 状态（{status_name}），"
                f"无法进入计算",
                code=StreamNotCheckedError.code,
                status=StreamNotCheckedError.status,
            )

    # Step 3：不可靠流守卫（既有 UnreliableStreamGuard）
    try:
        await UnreliableStreamGuard.check(db, ids)
    except PcsError as e:
        # 透传守卫的 PcsError 内容：保证 422 错误响应（code/status/message）
        # byte-for-byte 等价于直接调用 UnreliableStreamGuard.check
        raise StreamUnreliableError(
            str(e),
            code=e.code,
            status=e.status,
        ) from e


__all__ = [
    "StreamNotCheckedError",
    "StreamNotFoundError",
    "StreamUnreliableError",
    "check_calc_inputs",
]