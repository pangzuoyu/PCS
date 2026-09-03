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
