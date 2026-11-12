"""AI 审计的**入队**（P10-A · Task T10）—— **失败降级，不抛**。

## 为什么和 `app/services/report/arq_queue.py` 分成两个

- **报表入队**（`report/arq_queue.py`）失败时抛 `PcsError(503)`
  ⇒ 「没入队」必须让端点知道（前端拿着空 task_id 会一直转圈）。
- **AI 审计入队**失败时**返回 False + warning**
  ⇒ 审计是**旁路** —— 审计挂了不该让 AI 端点 503。

⇒ **不要**复用报表那个 `_enqueue`（它失败就抛 ⇒ 端点 503 ⇒ 审计拖死业务）。

## 为什么入队的是**函数名字符串**

ARQ 0.28 的 `serialize_job` 把首参当**函数名**存进队列，worker 端用
`self.functions[函数名]` 查 ⇒ 传函数对象的话，入队成功、worker 找不到
⇒ job 静默失败（报表那条链路已踩过，见 `report/arq_queue.py` 的头注）。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

#: **入队超时**（评审 #16 · 2026-11-12）—— Redis 不可达时**快速失败**。
#: ⚠️ 入队是在中间件的 `finally` 里 await 的 ⇒ 超时就是**HTTP 连接被钉住的时长**
#: ⇒ 2 秒足够（Redis 在本机/内网）。
ENQUEUE_TIMEOUT_S = 2.0

#: **进程级连接池**（评审 #20）—— 懒创建、复用、lifespan 关闭。
#: ⚠️ 旧实现每个请求都建一个又拆一个 ⇒ 每次付一次 TCP 连接 + AUTH
#: ⇒ 而这条路径**注定**是未来的热路径。
_pool: Any | None = None
_pool_lock = asyncio.Lock()


async def _create_pool():
    """建 ARQ 连接池（**测试接缝**：测试会 monkeypatch 这个函数）。"""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    settings = RedisSettings.from_dsn(get_settings().redis_url)
    # ⚠️ **`conn_retries=0`**（评审 #16）—— ARQ 默认重试 5 次、间隔 1 秒
    # ⇒ Redis 不可达时一次入队要拖 **~10 秒**。
    settings.conn_retries = 0
    return await create_pool(settings)


async def _get_pool():
    """取**进程级**连接池（懒创建 + 并发安全）。"""
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await _create_pool()
    return _pool


def _reset_pool_cache() -> None:
    """**测试接缝**：清掉缓存的连接池（用例之间不留连接）。"""
    global _pool
    _pool = None


async def close_ai_audit_pool() -> None:
    """关闭进程级连接池（由 lifespan 的关闭钩子调用 · 评审 #20）。"""
    global _pool
    pool, _pool = _pool, None
    if pool is None:
        return
    try:
        await pool.aclose()
    except Exception:  # noqa: BLE001 — 关闭失败不该影响 shutdown
        logger.warning("关闭 AI 审计的 ARQ 连接失败", exc_info=True)


def _jsonable(fields: dict[str, Any]) -> dict[str, Any]:
    """把字段转成 **JSON 可序列化**的形状（ARQ 用 JSON 存 job 参数）。

    ⚠️ `uuid.UUID` **不是** JSON 可序列化的 ⇒ 不转的话入队直接失败。
    """
    out: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, uuid.UUID):
            out[key] = str(value)
        else:
            out[key] = value
    return out


async def enqueue_ai_audit_log(**fields: Any) -> bool:
    """把一条 AI 审计**入队**；成功返回 True，失败返回 False。

    ⚠️ **绝不抛** —— 失败降级为一条 warning（审计是旁路，不该拖死业务）。

    Returns:
        True ⇒ 已入队；False ⇒ 入队失败（已记 warning）。
    """
    from app.workers.ai_audit_tasks import write_ai_audit_log  # noqa: F401

    payload = _jsonable(fields)
    try:
        pool = await _get_pool()
        # ⚠️ 传**名字字符串**（不是函数对象）—— 见模块 docstring。
        # ⚠️ **超时兜底**（评审 #16）—— 入队在中间件的 `finally` 里 await
        # ⇒ 没有超时 ⇒ Redis 半死不活时**HTTP 连接被无限期钉住**。
        job = await asyncio.wait_for(
            pool.enqueue_job("write_ai_audit_log", **payload),
            timeout=ENQUEUE_TIMEOUT_S,
        )
    except TimeoutError:
        logger.warning("AI 审计入队超时（已降级，不影响请求）")
        return False
    except Exception as exc:  # noqa: BLE001 — Redis 各种连接异常
        logger.warning("AI 审计入队失败（已降级，不影响请求）: %s: %s", type(exc).__name__, exc)
        return False
    if job is None:
        logger.warning("AI 审计入队未返回任务句柄（已降级）")
        return False
    return True


__all__ = ["close_ai_audit_pool", "enqueue_ai_audit_log"]
