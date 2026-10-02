"""Async 5-min TTL 缓存 (仿 _compound_config_cache.py 但适配 AsyncSession).

P7 Sprint 2 F-P1-002 fix: ConfigEnergyConversionFactor 5-min TTL 缓存,
避免每次 summarize_energy_year 都全表读 (R1 26 行 + 后续可能 50+ 行).

差异:
- 用 ``asyncio.Lock`` 代替 threading.Lock (async 上下文)
- 用 ``time.monotonic()`` 缓存过期
- _load_async_fn 是 async coroutine, 直接 await

测试隔离: ``clear_all_caches()`` 让 vitest 重新加载 (避免 cache 跨测试污染).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Final

_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes per plan C5 Step 4
_TTL_CACHE_STATE: Final[dict[str, tuple[float, Any]]] = {}
_TTL_CACHE_LOCK: Final[asyncio.Lock] = asyncio.Lock()


async def get_or_reload_async[T](
    cache_key: str,
    loader_fn: Callable[[], Awaitable[T]],
) -> T:
    """TTL 缓存: 命中返回内存值, 过期或首次访问 await loader_fn() 重读.

    Args:
        cache_key: 缓存唯一键 (例如 'config_energy_conversion_factors')
        loader_fn: async DB 加载函数 (锁外 await, 避免长时持锁)

    Returns:
        loader_fn 返回值 (缓存内存版本)
    """
    now = time.monotonic()
    async with _TTL_CACHE_LOCK:
        entry = _TTL_CACHE_STATE.get(cache_key)
        if entry is not None and now - entry[0] <= _CACHE_TTL_SECONDS:
            return entry[1]  # type: ignore[return-value]
    # 锁外 await DB 加载 (避免阻塞其他 cache key)
    value = await loader_fn()
    async with _TTL_CACHE_LOCK:
        _TTL_CACHE_STATE[cache_key] = (time.monotonic(), value)
    return value


def clear_all_caches() -> None:
    """强制清空全部 TTL 缓存 (热重载 / 运营期手动触发 / 测试隔离).

    Synchronous 入口, 任何上下文可调 (无需 await).
    """
    _TTL_CACHE_STATE.clear()