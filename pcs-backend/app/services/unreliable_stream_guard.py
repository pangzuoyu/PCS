"""P3.x SIM-39 / TODO-037: 不可靠物流下游计算硬拒绝守卫。

背景（plan PCS-P3.2-SIM §self-review + 用户 2026-09-08 裁决）：
- P3.2 SIM-10 仅标记 `streams.is_unreliable=True`（NOT_CONVERGED/ABORTED
  单元产品），不阻止使用
- SIM-39 提前闭环：P4 工艺计算入口（POST /api/v1/calculate/...）调用本守卫；
  任意输入流 unreliable=True → 422 STREAM_UNRELIABLE_BLOCKED + 流名清单

不可靠数据进入计算会污染下游；仅标记不阻止等于没做。
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Stream
from app.services.exceptions import PcsError


class UnreliableStreamGuard:
    """下游计算输入流可靠性守卫（TODO-037 闭环）。"""

    @staticmethod
    async def check(
        db: AsyncSession,
        stream_ids: Iterable[uuid.UUID],
    ) -> dict[str, Any]:
        """校验输入物流集不含不可靠流。

        Args:
            db: async session
            stream_ids: 计算输入流 UUID 集（重复自动去重）

        Returns:
            dict 形如 {"checked": int, "unreliable_names": []}（直通时）

        Raises:
            PcsError 422 STREAM_UNRELIABLE_BLOCKED: 任意输入流
            is_unreliable=True（消息含全部不可靠流名，sorted）
        """
        ids = list(dict.fromkeys(stream_ids))
        if not ids:
            return {"checked": 0, "unreliable_names": []}

        unreliable_names = list(
            (
                await db.execute(
                    select(Stream.stream_name).where(
                        Stream.stream_id.in_(ids),
                        Stream.is_unreliable.is_(True),
                    )
                )
            ).scalars().all()
        )
        if unreliable_names:
            raise PcsError(
                f"输入物流含不可靠流（NOT_CONVERGED/ABORTED 单元产品），"
                f"拒绝下游计算：{sorted(unreliable_names)}",
                code="STREAM_UNRELIABLE_BLOCKED",
                status=422,
            )
        return {"checked": len(ids), "unreliable_names": []}


__all__ = ["UnreliableStreamGuard"]