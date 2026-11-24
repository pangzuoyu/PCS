"""`GET /status` 的守卫（P10-C · T1b · SPEC §7.22）。

## 本文件断什么

1. ⚠️ **要登录** —— 本端点吐的是**运维内部信息**（队列深度 / worker 心跳 /
   LDAP 主机 / DB 与 Redis 延迟）⇒ ⇒ ⇒ 匿名可读 = 给外人一张内部拓扑图
2. **恒 200** ⇒ ⇒ 组件挂了**页面也要打得开**（状态页的职责是**报告**，不是拒绝）
3. **五个组件**都在 ⇒ ⇒ database / redis / queue / ldap + 总体 status
4. ⚠️ **不含敏感值** ⇒ ⇒ 不出现 bind 密码 / DB 口令 / Redis URL
5. ⚠️ **不复用 `/health`** ⇒ ⇒ `/health` 是 liveness probe ⇒ ⇒ ⇒ 叠阻塞依赖
   ⇒ ⇒ ⇒ Redis 抖动 ⇒ ⇒ ⇒ 探针超时 ⇒ ⇒ ⇒ **服务重启循环**（ADR-0049 §⑥）
6. 队列深度用 **ZCARD**（ARQ 的队列是 zset ⇒ ⇒ ⇒ `LLEN` 恒 0 ⇒ ⇒ 会误报空）
"""
from __future__ import annotations

import uuid

import pytest

from app.api.v1.status import StatusResponse
from app.core.security import create_access_token


def _auth_headers() -> dict[str, str]:
    """Bearer token（**无行 ⇒ 放行** ⇒ ⇒ 不必建 `users` 行）。"""
    token = create_access_token(
        subject="test-status",
        role="DESIGNER",
        extra={"user_id": str(uuid.uuid4())},
    )
    return {"Authorization": f"Bearer {token}"}


async def test_status_requires_authentication(client) -> None:
    """⚠️ **没登录 ⇒ ⇒ 401** ⇒ ⇒ ⇒ 运维内部信息不外泄。

    ⇒ ⇒ ⇒ 恒 200 说的是「**组件**挂了仍 200」⇒ ⇒ ⇒ 不是「匿名也 200」。
    """
    resp = await client.get("/api/v1/status")
    assert resp.status_code == 401, resp.text


async def test_status_is_always_200(client) -> None:
    """⚠️ **恒 200** ⇒ ⇒ 页面永远打得开 ⇒ ⇒ ⇒ 红了的是组件字段，不是 HTTP 码。"""
    resp = await client.get("/api/v1/status", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "down", "unknown")


async def test_status_contains_all_components(client) -> None:
    """⚠️ 五个组件都要在 ⇒ ⇒ 前端能逐项渲染。"""
    resp = await client.get("/api/v1/status", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("database", "redis", "queue", "ldap"):
        assert key in body, f"缺组件 {key}"
        assert body[key]["status"] in ("ok", "degraded", "down", "unknown")
    assert "checked_at" in body


async def test_status_does_not_leak_secrets(client) -> None:
    """⚠️ **不含敏感值** ⇒ ⇒ 状态页是「给人看的」⇒ ⇒ ⇒ 不能带凭据。

    ⇒ ⇒ ⇒ LDAP 的 bind 密码 / DB 口令 / Redis URL **都不许**出现。
    """
    resp = await client.get("/api/v1/status", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.text
    for secret_marker in ("bind_password", "postgres://", "redis://", "password"):
        assert secret_marker not in body, f"响应里出现了敏感片段：{secret_marker}"


async def test_status_queue_component_has_the_expected_shape(client) -> None:
    """⚠️ 队列组件的字段集要**固定** ⇒ ⇒ 前端按字段渲染 ⇒ ⇒ 不能变。"""
    resp = await client.get("/api/v1/status", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    queue = resp.json()["queue"]
    assert set(queue) == {"status", "depth", "worker_last_heartbeat", "worker_alive"}


def test_status_response_schema_is_stable() -> None:
    """⚠️ **响应结构钉死** ⇒ ⇒ 前端类型生成不会因为一次改动而漂。"""
    assert set(StatusResponse.model_fields) == {
        "status",
        "checked_at",
        "database",
        "redis",
        "queue",
        "ldap",
    }


def test_ldap_url_credentials_are_redacted() -> None:
    """⚠️ **URL 里的凭据要抹掉** ⇒ ⇒ 状态页**人人可看** ⇒ ⇒ ⇒ 凭据不能原样回显。

    ⇒ ⇒ ⇒ `ldaps://cn=admin:secret@host` 这种写法并不罕见 ⇒ ⇒ ⇒ 回显即泄漏。
    """
    from app.api.v1.status import _redact_url

    assert _redact_url("ldaps://cn=admin:secret@ldap.internal:636") == (
        "ldaps://***@ldap.internal:636"
    )
    assert _redact_url("ldap://localhost:389") == "ldap://localhost:389"


async def test_health_endpoint_does_not_grow_the_status_dependencies(client) -> None:
    """⚠️ **`/health` 不能被状态页「污染」** ⇒ ⇒ 它仍是 liveness probe。

    ⇒ ⇒ ⇒ `/health` 的响应**不含**队列深度 / worker 心跳 / LDAP
    ⇒ ⇒ ⇒ ⇒ 即便有人把 status 的探测塞进 health ⇒ ⇒ ⇒ 这里也会红。
    """
    # ⚠️ 真实路径是 `/api/v1/health`（health router 无 prefix ⇒ ⇒ 挂在
    # ⇒ ⇒ `api_router`（prefix `/api/v1`）下）
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"status", "database", "realtime", "realtime_reason"}
