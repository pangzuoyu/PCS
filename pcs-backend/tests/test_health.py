"""健康检查端点测试：database up/down 与未捕获异常均走 ErrorResponse 信封。

覆盖 /api/v1/health 三场景：DB up → ok / DB down → degraded /
未捕获异常 → 500 INTERNAL_ERROR 信封（含 trace_id）。
"""
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok(monkeypatch) -> None:
    import app.api.v1.health as health_mod

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_mod, "check_database_async", _ok)
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert body["database"] in ("up", "down")


def test_health_db_down(monkeypatch) -> None:
    import app.api.v1.health as health_mod

    async def _down() -> bool:
        return False

    monkeypatch.setattr(health_mod, "check_database_async", _down)
    resp = TestClient(create_app()).get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded" and body["database"] == "down"


def test_unhandled_exception_500_envelope(monkeypatch) -> None:
    import app.api.v1.health as health_mod

    async def _boom() -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(health_mod, "check_database_async", _boom)
    resp = TestClient(create_app(), raise_server_exceptions=False).get(
        "/api/v1/health"
    )
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "INTERNAL_ERROR" and body["trace_id"]


async def test_unit_lane_health_probe_never_touches_the_real_db(client) -> None:
    """⚠️ **bug-2162 的回归钉子** —— 守卫不能是**空壳**。

    ## 背景

    `tests/conftest.py::_avoid_real_db_probe`（autouse）声称「patch 掉
    health 的 DB 探测，避免单测连真库」⇒ 但它只 patch 了**定义处**
    （`app.db.session.check_database_async`）⇒ 而消费者
    （`app/api/v1/health.py`）是 **`from ... import` 按值导入**的
    ⇒ 补丁**够不着它** ⇒ 守卫一直是空壳 ⇒ 单测真的连了**开发库**。

    ## 后果（不是「脏」而已，是**别的用例会红**）

    探测会创建**模块级单例**的 async engine ⇒ 那条连接绑定在
    **当时那个 event loop** 上 ⇒ 用例结束、loop 关闭、引擎还在
    ⇒ **下一个文件的下一个 loop** 从池里拿到它 ⇒ asyncpg 报
    「Future attached to a different loop」
    ⇒ 受害者是**别的文件**的用例（实测：`test_ws_notifications.py`）
    ⇒ 症状离病因很远 ⇒ 极难自查。

    ## 断言

    打过 `/api/v1/health` 之后，**全局 async engine 必须仍是 None**
    ⇒ 单测车道**没有**碰真库 ⇒ 也不会有跨 loop 的连接残留。
    """
    import app.db.session as db_session

    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200, resp.text
    assert db_session._async_engine is None, (
        "单测车道创建了全局 async engine ⇒ 它连的是**真库**，且它的连接"
        "绑定在本用例的 event loop 上 ⇒ 下一个文件的用例会拿到"
        "「attached to a different loop」的连接而红（bug-2162）"
    )
