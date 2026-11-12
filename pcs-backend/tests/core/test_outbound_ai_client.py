"""`AINotImplementedError` + 全局 501 handler + `OutboundAIClient`（P10-A · Task T8）。

## 这个模块的形状

P10 阶段 AI **只做预留**：路由一律 501，但**审计链路是完整的** ——
「AI 还没上线」≠「AI 调用不用留痕」。

⇒ `OutboundAIClient.call()` 的顺序是**固定**的：
① **调用时二次校验** endpoint（DNS 会漂移 ⇒ 启动时过了不代表此刻还成立）
② 脱敏 ③ 审计 ④ 抛 `AINotImplementedError`（**不真调**）。

## 三条容易写错的

1. **审计失败不得抛** —— 否则「AI 调用因审计挂掉」⇒ 审计必须降级。
2. **脱敏在审计之前** —— 审计里存的是**脱敏后**的载荷 ⇒ 审计表里不落原文。
3. **端点校验在发出任何请求之前** —— 校验不过就**不许**有请求发出去。
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.ai_errors import AINotImplementedError
from app.core.ai_sanitizer import sanitize_for_ai
from app.core.errors import install_exception_handlers
from app.core.outbound_ai_client import OutboundAIClient


@pytest.fixture
def ai_app() -> FastAPI:
    """最小 app：只装全局异常处理器 + 一个抛 `AINotImplementedError` 的端点."""
    app = FastAPI(title="PCS AI Test")
    install_exception_handlers(app)

    @app.get("/boom")
    async def _boom() -> None:
        raise AINotImplementedError()

    return app


async def test_ai_not_implemented_error_becomes_501_with_request_id(ai_app) -> None:
    """抛 AINotImplementedError ⇒ 501 + 信封含 code/message/request_id。"""
    transport = ASGITransport(app=ai_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/boom")

    assert resp.status_code == 501, resp.text
    body = resp.json()
    assert body["code"] == "AI_NOT_IMPLEMENTED"
    assert body["message"]
    # 没有中间件时也要有 request_id（回退成 uuid4）
    uuid.UUID(body["request_id"])
    # SPEC §4.1.1 的形状
    assert body["status"] == "not_implemented"


async def test_outbound_client_validates_endpoint_before_calling() -> None:
    """endpoint 不在内网 CIDR ⇒ RuntimeError（**且没发出任何请求**）。"""
    called: list[dict] = []

    async def audit_fn(payload: dict) -> None:
        called.append(payload)

    client = OutboundAIClient(
        endpoint="8.8.8.8", timeout=30, cidrs=["10.0.0.0/8"], audit_fn=audit_fn
    )

    with pytest.raises(RuntimeError):
        await client.call({"text": "x"})

    assert called == [], "校验没过就审计 ⇒ 顺序错了"


async def test_outbound_client_sanitizes_payload_before_audit() -> None:
    """进 `_audit` 的 payload 已脱敏（邮箱被替换）。

    ⚠️ **靠注入的 `audit_fn` 观察** —— `_audit` 默认是 no-op ⇒ 没有别的观察点。
    """
    seen: list[dict] = []

    async def audit_fn(payload: dict) -> None:
        seen.append(payload)

    client = OutboundAIClient(
        endpoint="10.1.2.3", timeout=30, cidrs=["10.0.0.0/8"], audit_fn=audit_fn
    )

    with pytest.raises(AINotImplementedError):
        await client.call({"text": "联系 someone@example.com"})

    assert seen, "审计没被调用"
    assert "someone@example.com" not in str(seen[0])
    assert seen[0] == sanitize_for_ai({"text": "联系 someone@example.com"})


async def test_outbound_client_raises_ai_not_implemented() -> None:
    """P10 阶段：脱敏 + 审计后抛 AINotImplementedError（**不真调**）。"""
    client = OutboundAIClient(
        endpoint="10.1.2.3", timeout=30, cidrs=["10.0.0.0/8"]
    )

    with pytest.raises(AINotImplementedError):
        await client.call({"text": "x"})


async def test_outbound_client_audit_failure_does_not_propagate() -> None:
    """⚠️ 审计写库失败**不得抛**（降级）—— 否则 AI 调用因审计挂掉。"""

    async def broken_audit(payload: dict) -> None:
        raise RuntimeError("审计库挂了")

    client = OutboundAIClient(
        endpoint="10.1.2.3", timeout=30, cidrs=["10.0.0.0/8"], audit_fn=broken_audit
    )

    # ⇒ 抛的是「未实现」，**不是**审计的 RuntimeError
    with pytest.raises(AINotImplementedError):
        await client.call({"text": "x"})


async def test_outbound_client_without_audit_fn_still_works() -> None:
    """没有注入 `audit_fn` 时 `_audit` 是 no-op（不炸）。"""
    client = OutboundAIClient(endpoint="10.1.2.3", timeout=30, cidrs=["10.0.0.0/8"])

    with pytest.raises(AINotImplementedError):
        await client.call({"text": "x"})
