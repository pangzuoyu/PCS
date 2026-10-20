"""Health endpoint（async via check_database_async，Sprint 1）。

P9A 扩 `realtime` / `realtime_reason`（ADR-0049 §⑥ / SPEC P9A-NOT-006）。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_database_async

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """健康检查响应（GET /health）。

    业务：status 服务整体状态（ok/degraded）+ database DB 连接状态（up/down）
    + realtime WS 推送通道状态（ok/degraded）；用于 K8s liveness probe 与
    监控告警（**始终 200**，由调用方按字段判定）。

    ⚠️ `realtime` **不得**纳入 liveness / readiness 判定 —— Redis 挂了会触发
    **服务重启循环**。需要 readiness probe 时另建端点，不复用 `/health`。
    """

    status: str
    database: str
    #: 实时推送（Redis pub/sub）通道状态。**仅供观测。**
    realtime: str
    #: 枚举：redis_unavailable / redis_timeout / pubsub_error / null。
    #: 自由字符串会让前端无法可靠判断该不该切轮询。
    realtime_reason: str | None


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """GET /health（liveness + DB 探测）。

    步骤：
    1. 调 check_database_async（asyncpg SELECT 1）探测 DB 连接
    2. 返回 {status, database}：db ok → "ok"/"up"，db fail → "degraded"/"down"
    3. **读 broadcaster 维护的状态标志**得出 realtime —— **零额外探测**
       （ADR-0049 §⑥ 约束 1：`/health` 已经在同步探测 DB，不能再叠第二个
       阻塞依赖；比「加超时」更好：既不占连接池，也不拖响应）
    4. 始终 200，由调用方按字段判定

    ⚠️ **语义精确性**：`realtime` 检测的是 **pub/sub 通道可达性**，不是
    Redis 整体健康。二者当前等价（同一个 Redis），但它只承诺「WS 推送能力」。
    排障时不得把 `realtime = degraded` 当作「Redis 挂了」的唯一判据 ——
    应结合 ARQ 队列状态与 `database` 字段综合判断。
    """
    from app.services.broadcaster import get_broadcaster

    db_ok = await check_database_async()
    broadcaster = get_broadcaster()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="up" if db_ok else "down",
        realtime=broadcaster.status,
        realtime_reason=broadcaster.reason,
    )