"""Health endpoint（async via check_database_async，Sprint 1）。

P9A 扩 `realtime` / `realtime_reason`（ADR-0049 §⑥ / SPEC P9A-NOT-006）。
P10-A 扩 `GET /health/ai`（AI 服务状态，SPEC §3.1.2 · §3.2.1(5)）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import check_database_async, get_db

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

class HealthAIResponse(BaseModel):
    """AI 健康状态（GET /health/ai）。

    ⚠️ **恒 200** —— 健康端点的职责是**报告**，不是**拒绝**：
    探针（K8s liveness）不该因为「AI 还没上线」而红。

    字段：
    - `status`：`not_configured`（没配 endpoint）/ `ok`（IP 字面量在内网）/
      `degraded`（配了但验证不过 / CIDR 非法 / 是域名没法验证）
    - `reason`：为什么是 degraded（`None` ⇒ 没毛病）
    - `ai_enabled`：系统参数 `ai_enabled`（**单一真相源**）
    - `endpoint_configured`：有没有 endpoint（系统参数优先，空则回退 env）
    - `cidrs_configured`：**`parse_cidrs()` 之后**非空（不是原始串非空）
    """

    status: str
    reason: str | None
    ai_enabled: bool
    endpoint_configured: bool
    cidrs_configured: bool


#: endpoint 是**域名**时的 reason（DNS **不解析** ⇒ 没法验证是否在内网）。
_REASON_DOMAIN = "endpoint_is_domain_not_verified"
#: endpoint 是 IP 但不在 CIDR 内。
_REASON_NOT_IN_CIDRS = "endpoint_not_in_cidrs"
#: `INTERNAL_CIDRS` 非法。
_REASON_INVALID_CIDRS = "invalid_cidrs"
#: 读不到系统参数。
_REASON_SETTINGS_UNAVAILABLE = "settings_unavailable"


def _is_ip_literal(host: str) -> bool:
    """host 是不是 IP 字面量（不是域名）。"""
    import ipaddress

    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


@router.get("/health/ai", response_model=HealthAIResponse)
async def health_ai(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthAIResponse:
    """GET /health/ai（AI 服务状态 · 预留）。

    ## 判定口径（写清楚，否则「为什么不是 ok」没法解释）

    | endpoint 形态 | 判定 | `status` |
    |---|---|---|
    | 未配置 | 不判 | `not_configured` |
    | **IP 字面量** | 本地比对 CIDR（**不联网**） | 在内网 ⇒ `ok`；不在 ⇒ `degraded` |
    | **域名** | **不解析 DNS** | 恒 `degraded` |

    ⇒ **域名 endpoint 永远不会是 `ok`** —— 这是**如实**的：
    没验证过就不能说它在内网。
    ⇒ **不解析 DNS** 还有一条工程理由：健康检查**不该依赖外网**
    （被墙/超时 ⇒ 探针抖动 ⇒ 误报故障）。
    """
    from app.core.ai_cidr import host_of, ip_in_cidrs, parse_cidrs
    from app.core.config import get_settings
    from app.services.system_setting_service import get_setting_value

    settings = get_settings()

    # ⚠️ **非法 CIDR 不许让健康端点崩** ⇒ 降级为「没配」+ 明确 reason。
    invalid_cidrs = False
    try:
        cidrs = parse_cidrs(settings.internal_cidrs)
    except RuntimeError:
        cidrs = []
        invalid_cidrs = True

    ai_enabled = False
    endpoint: str | None = None
    try:
        ai_enabled = bool(await get_setting_value(db, "ai_enabled", default=False))
        endpoint = (await get_setting_value(db, "ai_endpoint", default=None)) or (
            settings.ai_endpoint
        )
    except Exception:  # noqa: BLE001 — 读不到参数不该让健康端点崩
        return HealthAIResponse(
            status="degraded",
            reason=_REASON_SETTINGS_UNAVAILABLE,
            ai_enabled=False,
            endpoint_configured=False,
            cidrs_configured=bool(cidrs),
        )

    if invalid_cidrs:
        return HealthAIResponse(
            status="degraded",
            reason=_REASON_INVALID_CIDRS,
            ai_enabled=ai_enabled,
            endpoint_configured=bool(endpoint),
            cidrs_configured=False,
        )

    if not endpoint:
        return HealthAIResponse(
            status="not_configured",
            reason=None,
            ai_enabled=ai_enabled,
            endpoint_configured=False,
            cidrs_configured=bool(cidrs),
        )

    # ⚠️ **复用 `ai_cidr.host_of`**（唯一的一份解析）—— 内联副本会让
    #    「健康端点的判断」与「启动校验 / 调用时校验」口径分叉（评审 M-6）。
    host = host_of(endpoint)

    if not _is_ip_literal(host):
        # ⚠️ 域名 ⇒ **不解析 DNS** ⇒ 恒 degraded（如实：没验证过）。
        return HealthAIResponse(
            status="degraded",
            reason=_REASON_DOMAIN,
            ai_enabled=ai_enabled,
            endpoint_configured=True,
            cidrs_configured=bool(cidrs),
        )

    if ip_in_cidrs(host, cidrs):
        return HealthAIResponse(
            status="ok",
            reason=None,
            ai_enabled=ai_enabled,
            endpoint_configured=True,
            cidrs_configured=bool(cidrs),
        )

    return HealthAIResponse(
        status="degraded",
        reason=_REASON_NOT_IN_CIDRS,
        ai_enabled=ai_enabled,
        endpoint_configured=True,
        cidrs_configured=bool(cidrs),
    )
