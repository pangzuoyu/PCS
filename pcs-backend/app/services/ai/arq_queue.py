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

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


async def _create_pool():
    """建 ARQ 连接池（**测试接缝**：测试会 monkeypatch 这个函数）。"""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.core.config import get_settings

    return await create_pool(RedisSettings.from_dsn(get_settings().redis_url))


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
    pool = None
    try:
        pool = await _create_pool()
        # ⚠️ 传**名字字符串**（不是函数对象）—— 见模块 docstring。
        job = await pool.enqueue_job("write_ai_audit_log", **payload)
    except Exception as exc:  # noqa: BLE001 — Redis 各种连接异常
        logger.warning("AI 审计入队失败（已降级，不影响请求）: %s: %s", type(exc).__name__, exc)
        return False
    finally:
        if pool is not None:
            try:
                await pool.aclose()
            except Exception:  # noqa: BLE001 — 关连接失败不该影响返回值
                logger.warning("关闭 AI 审计的 ARQ 连接失败", exc_info=True)
    if job is None:
        logger.warning("AI 审计入队未返回任务句柄（已降级）")
        return False
    return True


__all__ = ["enqueue_ai_audit_log"]
