"""`GET /api/v1/health/ai`（P10-A · Task T12）。

## 判定口径（写清楚，否则「为什么不是 ok」没法解释）

| endpoint 形态 | 判定 | `status` |
|---|---|---|
| 未配置 | 不判 | `not_configured` |
| **IP 字面量** | 本地比对 CIDR（**不联网**） | 在内网 ⇒ `ok`；不在 ⇒ `degraded` |
| **域名** | **不解析 DNS** | 恒 `degraded` + `reason="endpoint_is_domain_not_verified"` |

⇒ **域名 endpoint 永远不会是 `ok`** —— 这是**如实**的：没验证过就不能说它在内网。
⇒ 健康端点**恒 200**（探针不因 AI 未配置而红）。

## 两条容易写错的

1. **`cidrs_configured` 的判据 = `parse_cidrs()` 之后非空**（不是原始串非空）。
2. **非法 CIDR 不许让健康端点崩** —— `parse_cidrs` 会抛 `RuntimeError`
   ⇒ 必须降级为 `cidrs_configured=False` + `reason="invalid_cidrs"`。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.system_setting_service import seed_defaults

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession) -> AsyncSession:
    await seed_defaults(db_session)
    await db_session.commit()
    return db_session


def _set_cidrs(monkeypatch, value: str) -> None:
    monkeypatch.setattr(get_settings(), "internal_cidrs", value)


async def test_health_ai_reports_not_configured_by_default(client, seeded) -> None:
    """默认 ⇒ status='not_configured'，且 **始终 200**（不因 AI 未配置而报错）。"""
    resp = await client.get("/api/v1/health/ai")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "not_configured"
    assert body["ai_enabled"] is False
    assert body["endpoint_configured"] is False
    assert body["cidrs_configured"] is False


async def test_health_ai_reports_ok_for_private_ip_endpoint(
    client, seeded, monkeypatch
) -> None:
    """IP 字面量 endpoint 在内网 ⇒ `ok`。"""
    _set_cidrs(monkeypatch, "10.0.0.0/8")
    await _set_setting(seeded, "ai_endpoint", "10.1.2.3")
    await _set_setting(seeded, "ai_enabled", True)

    resp = await client.get("/api/v1/health/ai")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["endpoint_configured"] is True
    assert body["cidrs_configured"] is True


async def test_health_ai_reports_endpoint_not_in_cidrs(client, seeded, monkeypatch) -> None:
    """endpoint 是 **IP 字面量**且不在 CIDR 内 ⇒ 'degraded'（**不是** 500）。"""
    _set_cidrs(monkeypatch, "10.0.0.0/8")
    await _set_setting(seeded, "ai_endpoint", "8.8.8.8")
    await _set_setting(seeded, "ai_enabled", True)

    resp = await client.get("/api/v1/health/ai")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["reason"]


async def test_health_ai_does_not_resolve_dns_for_a_domain_endpoint(
    client, seeded, monkeypatch
) -> None:
    """⚠️ **域名 endpoint 不做 DNS 解析** ⇒ 恒 degraded +
    reason='endpoint_is_domain_not_verified'。

    ⚠️ **必须断言「没解析 DNS」** —— 若中间件/健康端点偷偷解析了域名，
    健康检查会被网络拖慢（甚至被墙）⇒ 探针不该依赖外网。
    """
    import socket

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        raise AssertionError("健康端点不该解析 DNS")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    _set_cidrs(monkeypatch, "10.0.0.0/8")
    await _set_setting(seeded, "ai_endpoint", "ai.internal.example")
    await _set_setting(seeded, "ai_enabled", True)

    resp = await client.get("/api/v1/health/ai")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["reason"] == "endpoint_is_domain_not_verified"


async def test_health_ai_does_not_crash_on_invalid_cidrs(client, seeded, monkeypatch) -> None:
    """⚠️ **非法 CIDR 不许让健康端点崩** ⇒ 恒 200 +
    cidrs_configured=False + reason='invalid_cidrs'。
    """
    _set_cidrs(monkeypatch, "not-a-cidr")
    await _set_setting(seeded, "ai_endpoint", "10.1.2.3")
    await _set_setting(seeded, "ai_enabled", True)

    resp = await client.get("/api/v1/health/ai")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cidrs_configured"] is False
    assert body["reason"] == "invalid_cidrs"
    assert body["status"] == "degraded"


async def _set_setting(db: AsyncSession, key: str, value: object) -> None:
    """改一个系统参数（值是 JSONB ⇒ 直接赋值）。"""
    from app.models.system import SystemSetting

    row = await db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(setting_key=key, setting_value_json=value)
        db.add(row)
    else:
        row.setting_value_json = value
    await db.commit()
