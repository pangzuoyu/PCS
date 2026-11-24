"""`GET /status` —— **系统状态页**的数据源（P10-C · T1b · SPEC §7.22）。

## 与 `/health` 的区别（**别混**）

| | `/health` | `/status` |
|---|---|---|
| 用途 | **liveness probe**（K8s / compose healthcheck）| **给人看**的状态页 |
| 恒 200？| ✅ 必须恒 200（否则探针会把服务重启）| ❌ 允许非 200 |
| 内容 | DB + realtime 两项 | 五个组件的**明细** + 队列深度 + worker 心跳 |
| 依赖 | DB 探测 + broadcaster 的**内存态**标志 | Redis（队列深度 + worker 心跳）|

⚠️ **`/health` 绝不能被状态页复用** —— ADR-0049 §⑥ 约束 1：
`/health` 已经在同步探测 DB ⇒ ⇒ ⇒ 再叠一个阻塞依赖（Redis / LDAP）
⇒ ⇒ ⇒ 会拖慢探针 ⇒ ⇒ ⇒ Redis 抖动时探针超时 ⇒ ⇒ ⇒ **服务重启循环**。

⇒ ⇒ ⇒ `/status` 是**独立端点** ⇒ ⇒ ⇒ 慢一点没关系（人点的，不是探针）。

## ⚠️ **恒 200**

状态页的职责是**报告**，不是**拒绝** ⇒ ⇒ ⇒ 组件挂了也要把页面显示出来
⇒ ⇒ ⇒ 那个组件的 `status` 字段才是红的 ⇒ ⇒ ⇒ 页面本身**必须能打开**。

⚠️ **恒 200 的范围**：**组件**挂了仍 200 ⇒ ⇒ ⇒ 但**没登录**仍 401
⇒ ⇒ ⇒ ⇒ ⇒ 两个「恒 200」说的是不同的事。

## ⚠️ **不含敏感值**

⇒ ⇒ ⇒ 只报「通不通 / 有多深 / 什么时候心跳」⇒ ⇒ ⇒
**不报** LDAP 的 bind 密码、DB 的口令、Redis 的 URL。
"""
from __future__ import annotations

import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.auth import current_user

# ⚠️ **不要 prefix** —— 路由路径本身就是 `/status`
# ⇒ ⇒ prefix + path 同名 ⇒ ⇒ ⇒ 实际路径成 `/api/v1/status/status` ⇒ ⇒ ⇒ 404
router = APIRouter(tags=["status"])

#: 组件状态取值（**枚举** ⇒ ⇒ 前端能可靠判断该不该显示红色）
ComponentState = Literal["ok", "degraded", "down", "unknown"]


class ComponentStatus(BaseModel):
    """单个组件的状态。"""

    status: ComponentState = Field(..., description="ok / degraded / down / unknown")
    detail: str | None = Field(None, description="补充说明（**不含敏感值**）")
    latency_ms: float | None = Field(None, description="探测耗时（毫秒）")


class QueueStatus(BaseModel):
    """ARQ 队列状态。"""

    status: ComponentState
    depth: int | None = Field(None, description="队列里待处理的任务数")
    worker_last_heartbeat: str | None = Field(
        None, description="worker 最近一次心跳（ARQ 的 health-check 键的内容）"
    )
    worker_alive: bool | None = Field(
        None, description="心跳键是否存在（TTL 内 ⇒ ⇒ worker 活着）"
    )


class StatusResponse(BaseModel):
    """系统状态（**给状态页用的**）。"""

    status: ComponentState = Field(..., description="总体状态（任一组件 down ⇒ ⇒ degraded）")
    checked_at: float = Field(..., description="探测时刻（unix 秒）")
    database: ComponentStatus
    redis: ComponentStatus
    queue: QueueStatus
    ldap: ComponentStatus


async def _probe_database() -> ComponentStatus:
    """DB 探测（复用 `check_database_async` ⇒ ⇒ **零重复实现**）。"""
    from app.db.session import check_database_async

    started = time.perf_counter()
    ok = await check_database_async()
    latency = (time.perf_counter() - started) * 1000
    return ComponentStatus(
        status="ok" if ok else "down",
        detail=None if ok else "DB 探测失败",
        latency_ms=round(latency, 2),
    )


async def _probe_redis_and_queue() -> tuple[ComponentStatus, QueueStatus]:
    """Redis 探测 + ARQ 队列深度 + worker 心跳（**一次连接**读三样）。

    ⚠️ **队列是 zset**（ARQ 用 `zadd` 入队 ⇒ ⇒ ⇒ `ZCARD` 才对
    ⇒ ⇒ ⇒ `LLEN` 恒 0 ⇒ ⇒ ⇒ 会误报「队列空」）。
    """
    from arq.constants import default_queue_name

    from app.core.config import get_settings

    settings = get_settings()
    started = time.perf_counter()
    try:
        import redis.asyncio as aioredis

        client = aioredis.Redis.from_url(settings.redis_url)
        try:
            depth = int(await client.zcard(default_queue_name))
            heartbeat = await client.get(f"{default_queue_name}:health-check")
        finally:
            await client.aclose()
        redis_status = ComponentStatus(
            status="ok",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception as exc:  # noqa: BLE001 — 状态页**报告**失败，不抛
        redis_status = ComponentStatus(
            status="down", detail=f"Redis 探测失败：{type(exc).__name__}"
        )
        return redis_status, QueueStatus(status="unknown", depth=None)

    # ⚠️ **队列深度不在这儿喂 Prometheus** ⇒ ⇒ ⇒ 它由
    # ⇒ ⇒ ⇒ `app/core/metrics.py::ARQQueueDepthCollector` **scrape 时现读**
    # ⇒ ⇒ ⇒ ⇒ 在这里 `.set()` 的话 ⇒ ⇒ ⇒ 没人打开状态页就永远是 0
    # ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 告警成假告警（详见该 collector 的 docstring）。

    hb_text = heartbeat.decode() if isinstance(heartbeat, bytes) else heartbeat
    worker_alive = hb_text is not None
    return redis_status, QueueStatus(
        status="ok" if worker_alive else "degraded",
        depth=depth,
        worker_last_heartbeat=hb_text,
        worker_alive=worker_alive,
    )


def _redact_url(url: str) -> str:
    """把 URL 里的**凭据**抹掉（`user:pass@` ⇒ ⇒ `***:***@`）。

    ⚠️ **为什么**：状态页**恒 200 且人人可看** ⇒ ⇒ ⇒ 任何原样回显的 URL
    都可能是凭据的泄漏面（`ldaps://cn=admin:secret@host` 这种写法并不罕见）
    ⇒ ⇒ ⇒ 只留「哪台机器」，不留「怎么进去的」。
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    if not parts.netloc or "@" not in parts.netloc:
        return url
    userinfo, _, host = parts.netloc.rpartition("@")
    return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, parts.fragment))


def _probe_ldap() -> ComponentStatus:
    """LDAP 状态（**只报配置**，不真连）。

    ⚠️ **为什么不真连**：LDAP bind 要凭据 + 要等网络 ⇒ ⇒ ⇒ 慢且会失败
    ⇒ ⇒ ⇒ 状态页每次点都等它 ⇒ ⇒ ⇒ 体验差 ⇒ ⇒ ⇒ 而且它**没有密码**可用
    ⇒ ⇒ ⇒（bind 密码是 secret ⇒ ⇒ ⇒ 不该为了「探活」去用它）。

    ⇒ ⇒ ⇒ 真要确认 LDAP 通 ⇒ ⇒ ⇒ 看**登录**是否成功 ⇒ ⇒ ⇒ 那是另一个故事。
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.ldap_url:
        return ComponentStatus(status="unknown", detail="未配置 LDAP（本地开发常见）")
    return ComponentStatus(status="ok", detail=f"已配置（{_redact_url(settings.ldap_url)}）")


@router.get("/status", response_model=StatusResponse)
async def status(
    _user: Annotated[dict[str, Any], Depends(current_user)],
) -> StatusResponse:
    """系统状态（**恒 200** ⇒ ⇒ ⇒ 页面永远打得开）。

    ⚠️ **要登录**（`current_user`）—— 本端点吐的是**运维内部信息**
    （队列深度 / worker 心跳 / LDAP 主机 / DB 与 Redis 延迟）
    ⇒ ⇒ ⇒ 匿名可读 ⇒ ⇒ ⇒ 等于给外人一张**内部拓扑图**
    ⇒ ⇒ ⇒ ⇒ ⇒ （`/health` 匿名是可以的 —— 它只说「活着」）

    ⚠️ **恒 200 的范围**：**组件**挂了仍 200 ⇒ ⇒ ⇒ 但**没登录**仍 401
    ⇒ ⇒ ⇒ ⇒ ⇒ 两个「恒 200」说的是不同的事。
    """
    database = await _probe_database()
    redis_status, queue = await _probe_redis_and_queue()
    ldap = _probe_ldap()

    states = {database.status, redis_status.status, queue.status, ldap.status}
    if "down" in states:
        overall = "degraded"
    elif "degraded" in states:
        overall = "degraded"
    else:
        overall = "ok"

    return StatusResponse(
        status=overall,
        checked_at=time.time(),
        database=database,
        redis=redis_status,
        queue=queue,
        ldap=ldap,
    )


__all__ = ["ComponentStatus", "QueueStatus", "StatusResponse", "router"]
