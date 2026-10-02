"""In-process 滑动窗口 rate limit (F-P2-006 fix).

适用 single-instance 部署, 防 DOS via 重复点击 /energy-summary/aggregate。
多实例需换 Redis-backed 实现 (TODO: deploy multi-instance 时替换)。

接口:
- check_rate_limit(key, limit, window_seconds) -> bool  (True=允许, False=拒绝)
- clear_all_rate_limits()  测试隔离用
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Final

# (key, 调用时间戳 ms) — deque 自动 evict 过期 entry
_WINDOW_STATE: Final[dict[str, deque[float]]] = {}
_LOCK: Final[asyncio.Lock] = asyncio.Lock()


async def check_rate_limit(key: str, limit: int, window_seconds: float) -> bool:
    """返回 True=允许, False=拒绝 (limit 之内 / 之外).

    Args:
        key: 限流维度 (e.g. f"energy_summary_aggregate:{user_id}")
        limit: 窗口内允许的最大次数
        window_seconds: 窗口大小 (秒)
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    async with _LOCK:
        dq = _WINDOW_STATE.setdefault(key, deque())
        # evict 过期
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


def clear_all_rate_limits() -> None:
    """清空所有限流状态 (测试隔离 / 运营期手动触发)."""
    _WINDOW_STATE.clear()
