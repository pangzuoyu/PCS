"""`GET /metrics` —— Prometheus 抓取端点（P10-C · T1a（exporters）· 计划 `docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md`）。

## ⚠️ **为什么在根路径而不是 `/api/v1/metrics`**

Prometheus 的 `scrape_configs` 抓的是**服务根**（`http://backend:8000/metrics`）
⇒ ⇒ ⇒ 挂在 `/api/v1` 下要么改抓取路径、要么加 rewrite ⇒ ⇒ ⇒ 不如直接放根。

## ⚠️ **无鉴权**（这是刻意的）

`/metrics` 要被 Prometheus **匿名**抓取 ⇒ ⇒ ⇒ 加了鉴权就得配 token
⇒ ⇒ ⇒ ⇒ 而且它**只暴露计数器与延迟**（不含业务数据）⇒ ⇒ ⇒ ⇒
⇒ ⇒ ⇒ 但仍要**限制暴露面** ⇒ ⇒ ⇒ ⇒ **不映射到宿主端口**
⇒ ⇒ ⇒ ⇒ ⇒ 只在容器内网可达（见 `docker-compose.yml`）。

## ⚠️ **不登记进 OpenAPI**

⇒ ⇒ 它不是业务契约 ⇒ ⇒ ⇒ 进 OpenAPI 会让前端类型生成多一个端点
⇒ ⇒ ⇒ ⇒ `include_in_schema=False` ⇒ ⇒ ⇒ 契约零变化。
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus 抓取端点（Prometheus text exposition format）。

    ⚠️ **刻意是 `def`（同步），不是 `async def`** ⇒ ⇒ ⇒ FastAPI 把它
    丢进 threadpool ⇒ ⇒ ⇒ collector 里的**阻塞** Redis 读
    （`ARQQueueDepthCollector`）⇒ ⇒ ⇒ **不阻塞事件循环** ⇒ ⇒ ⇒
    ⇒ ⇒ ⇒ 否则一次 scrape 会把整个后端的请求卡住。
    """
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


__all__ = ["router"]
