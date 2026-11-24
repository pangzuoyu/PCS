"""Prometheus 指标（**exporters**）—— P10-C · T1a（exporters）· 计划 `docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md`。

## 这个模块放哪一层

**`app/core/`** ⇒ ⇒ core **不得** import api / services / models
（`tests/architecture/test_imports.py` 守着）⇒ ⇒ ⇒ 这里的代码只能碰
**starlette 的 request.scope** ⇒ ⇒ ⇒ 端点路由模板从那里取。

## ⚠️ **标签必须用「路由模板」而不是原始 URL**

`/api/v1/psychro/results/{record_id}` 是**模板**（有限个）
⇒ ⇒ 而 `/api/v1/psychro/results/9f3c-…` 是**原始 URL**（每个 id 一条）
⇒ ⇒ ⇒ 用原始 URL 当标签 ⇒ ⇒ ⇒ **基数无上界** ⇒ ⇒ ⇒ Prometheus 被打爆。

⇒ ⇒ ⇒ 中间件在响应回来之后读 `request.scope["route"].path`
⇒ ⇒ ⇒ 那是**模板** ✔ ⇒ ⇒ ⇒ 404（没匹配到路由）时退回固定串
`__unmatched__` ⇒ ⇒ ⇒ 不泄漏原始 URL。

### ⚠️⚠️ **标签里没有 `/api/v1` 前缀**（FastAPI 懒挂载的**后果**）

实测（FastAPI 0.141）：`scope["route"].path` = **相对 `/api/v1` 的**路径
⇒ ⇒ ⇒ `/api/v1/psychro/results/{record_id}` 的标签是
**`/psychro/results/{record_id}`** ⇒ ⇒ ⇒ 而**根路径**端点
（`/metrics`）的标签是**带**自己的完整路径的 ⇒ ⇒ ⇒ `/metrics`。

⚠️ **为什么改不了**：`scope["root_path"]` 是空的、`scope["router"].prefix`
也是空的 ⇒ ⇒ ⇒ 前缀在懒挂载里**没进 scope** ⇒ ⇒ ⇒ 拼不回来。

⚠️ **后果**：
① 标签**一致**（所有 `/api/v1/*` 端点都**不带**前缀）⇒ ⇒ ⇒ 不歧义；
② 基数**有上界** ✔（这才是要紧的）；
③ 看面板时要知道「`/psychro/...` = `/api/v1/psychro/...`」
⇒ ⇒ ⇒ **文档化**（本段 + `docs/deploy-prerequisites.md`）⇒ ⇒ ⇒ 而不是猜。

## ⚠️ `/metrics` **无鉴权**

⇒ ⇒ ⇒ 它**不映射到宿主端口** ⇒ ⇒ ⇒ 只在容器内网可达
⇒ ⇒ ⇒ ⇒ 同 `docker-compose.yml` 里「不映射端口」的那些服务。

## 指标清单

| 指标 | 类型 | 标签 | 谁喂它 | 断什么 |
|---|---|---|---|---|
| `pcs_http_requests_total` | Counter | method · path · status | 中间件 | 请求量与错误率 |
| `pcs_http_request_duration_seconds` | Histogram | method · path | 中间件 | P95 / P99 |
| `pcs_http_requests_in_flight` | Gauge | —— | 中间件 | 并发压力 |
| `pcs_db_pool_checked_out` | Gauge | engine | `app/db/session.py`（池事件）| 连接池是否打满 |
| `pcs_db_pool_size` | Gauge | engine | 同上 | 池上限 |
| `pcs_state_machine_transition_failures_total` | Counter | transition | `app/services/state_machine.py` | 签署链卡住 |
| `pcs_arq_queue_depth` | Gauge | queue | **collector（scrape 时现读）** | 异步任务积压 |

## ⚠️ **「定义了但没人喂」的指标 = 假零** ⇒ ⇒ ⇒ 一律不许留

`prometheus_client` 的 `Gauge` **创建即报 0** ⇒ ⇒ ⇒ 一个从来没人
`.set()` 过的 gauge ⇒ ⇒ ⇒ `/metrics` 上是 `xxx 0.0` ⇒ ⇒ ⇒ 面板上
**看起来「一切正常」** ⇒ ⇒ ⇒ 而真相是「**根本没测**」⇒ ⇒ ⇒ 假零。

⇒ ⇒ ⇒ 所以本模块里**每个** gauge / counter 都必须有喂它的地方
⇒ ⇒ ⇒ 「待签署数」原想放这儿 ⇒ ⇒ ⇒ **但没人知道「待签署」怎么算**
⇒ ⇒ ⇒（那是业务口径 ⇒ ⇒ ⇒ 要人裁）⇒ ⇒ ⇒ ⇒ ⇒ **先不放**
⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 留在 `docs/superpowers/plans/…p10-c…md` 的「未解决」里。
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Generator

from prometheus_client import REGISTRY, Counter, Gauge, Histogram
from prometheus_client.core import GaugeMetricFamily
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: 未匹配到路由的请求（404）⇒ ⇒ **不能**把原始 URL 当标签（基数无上界）
UNMATCHED_ROUTE = "__unmatched__"

#: 请求延迟直方图的桶（秒）⇒ ⇒ 覆盖「快（<0.1s）」到「慢（>10s）」
#: ⇒ ⇒ P95 / P99 的分位数靠它算 ⇒ ⇒ 桶太粗 ⇒ ⇒ 分位数没意义。
DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

#: 请求计数（method · path · status）
HTTP_REQUESTS_TOTAL = Counter(
    "pcs_http_requests_total",
    "HTTP 请求总数",
    ("method", "path", "status"),
)

#: 请求延迟（method · path）
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "pcs_http_request_duration_seconds",
    "HTTP 请求延迟（秒）",
    ("method", "path"),
    buckets=DURATION_BUCKETS,
)

#: 在飞请求数（并发压力）
HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "pcs_http_requests_in_flight",
    "正在处理中的 HTTP 请求数",
)

#: 状态机转移失败（签署链卡住的信号）
STATE_MACHINE_TRANSITION_FAILURES = Counter(
    "pcs_state_machine_transition_failures_total",
    "状态机转移被拒的次数",
    ("transition",),
)

#: DB 连接池（打满 ⇒ ⇒ 性能问题的先行指标）
#: ⚠️ **两个引擎**（sync / async）⇒ ⇒ ⇒ 用 `engine` 标签区分
#: ⇒ ⇒ ⇒ 否则「池打满」这句话说不清是哪个池。
DB_POOL_CHECKED_OUT = Gauge(
    "pcs_db_pool_checked_out",
    "DB 连接池已借出的连接数",
    ("engine",),
)
DB_POOL_SIZE = Gauge(
    "pcs_db_pool_size",
    "DB 连接池上限",
    ("engine",),
)


class ARQQueueDepthCollector:
    """ARQ 队列深度 —— **scrape 时现读 Redis**（而不是靠别人去 `.set()`）。

    ## ⚠️ **为什么不能用 `Gauge.set`**

    `Gauge.set` 只在**有人去设它**的时候才有值 ⇒ ⇒ ⇒ 若只在 `/status`
    里设 ⇒ ⇒ ⇒ **没人打开状态页 ⇒ 永远是 0** ⇒ ⇒ ⇒ 「队列积压」告警
    变成**永远不会触发的假告警**（且面板上显示 0 ⇒ ⇒ ⇒ 假零）。

    ⇒ ⇒ ⇒ 改成 **collector** ⇒ ⇒ ⇒ **每次 scrape 现读一次 Redis**。

    ## ⚠️ **读不到时「不产出序列」而不是报 0**

    ⇒ ⇒ ⇒ Redis 挂了 ⇒ ⇒ ⇒ 序列**消失** ⇒ ⇒ ⇒ 「测不到」与「真的是 0」
    在面板上**可区分**（`absent()` 告警能抓到前者）。

    ## ⚠️ **同步 Redis 客户端**

    `collect()` 是**同步**的 ⇒ ⇒ ⇒ 用 `redis.Redis`（阻塞）⇒ ⇒ ⇒
    ⇒ ⇒ ⇒ `/metrics` 端点必须声明成 **`def`（非 `async def`）**
    ⇒ ⇒ ⇒ ⇒ FastAPI 把它丢进 threadpool ⇒ ⇒ ⇒ 不阻塞事件循环。
    """

    def collect(self) -> Generator[GaugeMetricFamily, None, None]:
        """产出 `pcs_arq_queue_depth`（**读不到就不产出**）。"""
        from arq.constants import default_queue_name

        from app.core.config import get_settings

        try:
            import redis

            # ⚠️ **必须给超时** —— redis-py 默认**不超时** ⇒ ⇒ ⇒ Redis 被
            # ⇒ ⇒ ⇒ 黑洞掉（丢包不回 RST）⇒ ⇒ ⇒ 这一个 scrape 会**永久挂住**
            # ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ Prometheus 把目标标成 down ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 整个监控瞎掉。
            client = redis.Redis.from_url(
                get_settings().redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            try:
                depth = int(client.zcard(default_queue_name))
            finally:
                client.close()
        except Exception:  # noqa: BLE001 —— 采集失败**不该**把整个 scrape 打成 500
            return
        family = GaugeMetricFamily(
            "pcs_arq_queue_depth",
            "ARQ 队列里的待处理任务数",
            labels=["queue"],
        )
        family.add_metric([default_queue_name], depth)
        yield family


#: ⚠️ **collector 注册在模块导入时** ⇒ ⇒ ⇒ 只注册一次（重复注册会抛
#: ⇒ ⇒ ⇒ `Duplicated timeseries` ⇒ ⇒ ⇒ 整个进程起不来）。
REGISTRY.register(ARQQueueDepthCollector())


def route_template(request: Request) -> str:
    """请求的**路由模板**（不是原始 URL）⇒ ⇒ ⇒ 标签基数有上界。

    ⚠️ 404（没匹配到路由）⇒ ⇒ `scope["route"]` 不存在 ⇒ ⇒ 退回固定串
    ⇒ ⇒ ⇒ **不**把原始 URL 写进标签。
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or UNMATCHED_ROUTE


class PrometheusMiddleware(BaseHTTPMiddleware):
    """记录请求量 / 延迟 / 在飞数。

    ⚠️ **用 `BaseHTTPMiddleware`**（而不是裸 ASGI）⇒ ⇒ 因为要读
    `scope["route"]` ⇒ ⇒ ⇒ 那是**响应之后**才有的 ⇒ ⇒ ⇒ 裸 ASGI
    中间件在响应回来前拿不到路由模板。
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        method = request.method
        HTTP_REQUESTS_IN_FLIGHT.inc()
        started = time.perf_counter()
        status = 500  # ⇒ 未捕获异常 ⇒ ⇒ 由下游 handler 兜成 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - started
            HTTP_REQUESTS_IN_FLIGHT.dec()
            path = route_template(request)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed)


__all__ = [
    "ARQQueueDepthCollector",
    "DB_POOL_CHECKED_OUT",
    "DB_POOL_SIZE",
    "DURATION_BUCKETS",
    "HTTP_REQUEST_DURATION_SECONDS",
    "HTTP_REQUESTS_IN_FLIGHT",
    "HTTP_REQUESTS_TOTAL",
    "PrometheusMiddleware",
    "STATE_MACHINE_TRANSITION_FAILURES",
    "UNMATCHED_ROUTE",
    "route_template",
]
