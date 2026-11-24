"""`/metrics` 端点的守卫（P10-C · T1a（exporters）· 计划 `docs/superpowers/plans/2026-11-23-p10-c-deploy-observability.md`）。

## 本文件断什么

1. **`/metrics` 在**根路径**（不是 `/api/v1/metrics`）⇒ ⇒ Prometheus 抓服务根
2. 响应是 **Prometheus text exposition format** ⇒ ⇒ 含本仓的指标名
3. ⚠️ **标签基数有上界** —— N 个不同 id 的请求 ⇒ ⇒ **同一个标签**
   （用原始 URL 当标签 ⇒ ⇒ 基数无上界 ⇒ ⇒ Prometheus 被打爆）
4. 未匹配路由 ⇒ ⇒ 固定标签 `__unmatched__` ⇒ ⇒ **不泄漏原始 URL**
5. ⚠️ **不进 OpenAPI** ⇒ ⇒ 它不是业务契约 ⇒ ⇒ 契约零变化
6. ⚠️⚠️ **没有「假零」** —— 没人喂的 gauge **不许出现**
   （`prometheus_client` 的无标签 gauge 创建即报 `0.0`
   ⇒ ⇒ ⇒ 面板上读成「正常」⇒ ⇒ ⇒ 而真相是「根本没测」）
7. ⚠️ **测不到 ≠ 是 0** —— Redis 读不到 ⇒ ⇒ ⇒ 队列深度**不产出序列**
   （而不是报 0 ⇒ ⇒ ⇒ 否则「队列积压」告警永远显示正常）
"""
from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

#: 指标名（必须出现在 /metrics 的响应里）
EXPECTED_METRICS = (
    "pcs_http_requests_total",
    "pcs_http_request_duration_seconds",
    "pcs_http_requests_in_flight",
)


@pytest.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    """⚠️ **用 `create_app()`** ⇒ ⇒ ⇒ 测的是**真实接线**（含中间件与根路径挂载）。

    ⇒ ⇒ ⇒ 不能用 conftest 的 `client` fixture ⇒ ⇒ ⇒ 它只挂 `api_router`
    ⇒ ⇒ ⇒ ⇒ `/metrics`（挂**根路径**）压根不在那个 app 里 ⇒ ⇒ ⇒ 恒 404。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_db
    from app.main import create_app

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_metrics_is_served_at_the_root_path(client) -> None:
    """⚠️ Prometheus 抓的是**服务根** ⇒ ⇒ `/metrics` ⇒ ⇒ 不是 `/api/v1/metrics`。"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200, resp.text
    assert "text/plain" in resp.headers["content-type"]


async def test_metrics_body_contains_our_metric_names(client) -> None:
    """⚠️ 端点要**真的吐指标** ⇒ ⇒ 不是空 200。"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200, resp.text
    body = resp.text
    for name in EXPECTED_METRICS:
        assert name in body, f"响应里没有 {name}"


async def test_metric_labels_use_the_route_template_not_the_raw_url(client) -> None:
    """⚠️⚠️ **基数上界** —— 这是 Prometheus 被打爆的唯一原因。

    ⇒ ⇒ 用**路由模板**当标签 ⇒ ⇒ ⇒ N 个不同 id ⇒ ⇒ **同一条**序列。
    """
    for i in range(3):
        record_id = uuid.UUID(int=i)
        await client.get(f"/api/v1/psychro/results/{record_id}")

    resp = await client.get("/metrics")
    body = resp.text
    series = [
        line
        for line in body.split("\n")
        if line.startswith("pcs_http_requests_total{") and "psychro" in line
    ]
    assert series, "没有 psychro 的请求计数 ⇒ ⇒ 指标没被记录"
    # ⇒ ⇒ 三次请求 ⇒ ⇒ **一条**序列（标签相同 ⇒ ⇒ 值累加）
    assert len(series) == 1, f"出现了 {len(series)} 条不同标签的序列 ⇒ ⇒ 基数无上界：{series}"
    # ⇒ ⇒ 而且原始 id **不能**出现在标签里
    assert not re.search(r"psychro/results/[0-9a-f-]{36}", body), (
        "原始 URL 进了标签 ⇒ ⇒ 每次请求都新增一条序列 ⇒ ⇒ 基数无上界"
    )


async def test_unmatched_routes_use_a_fixed_label(client) -> None:
    """⚠️ 404 ⇒ ⇒ `scope["route"]` 不存在 ⇒ ⇒ 固定串 ⇒ ⇒ 不泄漏原始 URL。"""
    await client.get("/api/v1/definitely-not-a-real-route-xyz")
    resp = await client.get("/metrics")
    assert "__unmatched__" in resp.text
    assert "definitely-not-a-real-route-xyz" not in resp.text


def test_metrics_endpoint_is_not_in_the_openapi_contract() -> None:
    """⚠️ **不进 OpenAPI** ⇒ ⇒ 前端类型生成不受影响 ⇒ ⇒ 契约零变化。"""
    from app.main import create_app

    schema = create_app().openapi()
    assert "/metrics" not in schema["paths"], (
        "/metrics 进了 OpenAPI ⇒ ⇒ 前端 `api:gen` 会多出一个端点"
        " ⇒ ⇒ 契约被迫变更（而它不是业务契约）"
    )


async def test_no_never_fed_gauges_are_exposed(client) -> None:
    """⚠️⚠️ **「定义了但没人喂」的 gauge = 假零** ⇒ ⇒ ⇒ 一律不许出现在 `/metrics`。

    ⇒ ⇒ ⇒ `prometheus_client` 的**无标签** gauge 创建即报 `0.0`
    ⇒ ⇒ ⇒ ⇒ ⇒ 面板上读成「一切正常」⇒ ⇒ ⇒ 而真相是「**根本没测**」。

    ⇒ ⇒ ⇒ 之前有个 `pcs_signatures_pending`（待签署数）就是这种
    ⇒ ⇒ ⇒ ⇒ 「业务口径没人裁 ⇒ ⇒ ⇒ 没人喂 ⇒ ⇒ ⇒ 却报 0」
    ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ **已删**（留在计划的「未解决」里）。
    """
    resp = await client.get("/metrics")
    body = resp.text
    assert "pcs_signatures_pending" not in body, (
        "有个从来没被喂过的 gauge ⇒ ⇒ 它报的是**假零**"
    )


async def test_queue_depth_is_absent_when_redis_is_unreachable(client) -> None:
    """⚠️ **测不到 ≠ 是 0** ⇒ ⇒ ⇒ Redis 读不到 ⇒ ⇒ ⇒ **序列不产出**。

    ⇒ ⇒ ⇒ 默认车道把 `redis_url` 指向 `127.0.0.1:1`（**必然连不上**）
    ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ ⇒ 于是这里断的正是「**fail-soft**」这条行为。
    ⇒ ⇒ ⇒ 若这里改成报 0 ⇒ ⇒ ⇒ 「队列积压」告警会永远显示「正常」。
    """
    resp = await client.get("/metrics")
    body = resp.text
    assert "pcs_arq_queue_depth" not in body, (
        "Redis 明明连不上 ⇒ ⇒ ⇒ 队列深度**不该**有序列"
        " ⇒ ⇒ ⇒（报 0 = 假零 ⇒ ⇒ ⇒ 告警会永远显示正常）"
    )
