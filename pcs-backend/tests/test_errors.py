from fastapi.testclient import TestClient

from app.main import create_app


def test_404_uses_envelope() -> None:
    resp = TestClient(create_app()).get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "HTTP_404" and body["trace_id"]


def test_405_uses_envelope() -> None:
    resp = TestClient(create_app()).post("/api/v1/health")
    assert resp.status_code == 405
    assert resp.json()["code"] == "HTTP_405"
