"""Contrats du prototype : refuser les appels coûteux non autorisés."""
from fastapi.testclient import TestClient
import app


def test_health_has_no_secret(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-do-not-expose")
    response = TestClient(app.app).get("/health")
    assert response.status_code == 200
    assert "test-key-do-not-expose" not in response.text
    assert response.json()["status"] == "ok"


def test_probe_refuses_missing_or_wrong_token_before_work(monkeypatch):
    monkeypatch.setenv("STEP0_PROBE_TOKEN", "correct-test-token")
    monkeypatch.setattr(app, "run_probe", lambda: (_ for _ in ()).throw(AssertionError("expensive work called")))
    client = TestClient(app.app)
    assert client.post("/probe").status_code == 401
    assert client.post("/probe", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_disabled_probe_refuses_even_matching_empty_auth(monkeypatch):
    monkeypatch.delenv("STEP0_PROBE_TOKEN", raising=False)
    client = TestClient(app.app)
    assert client.post("/probe", headers={"Authorization": "Bearer "}).status_code == 503


def test_authorized_probe_runs_fixed_fixture(monkeypatch):
    monkeypatch.setenv("STEP0_PROBE_TOKEN", "correct-test-token")
    monkeypatch.setattr(app, "run_probe", lambda: {"status": "passed", "fixture": "iris"})
    response = TestClient(app.app).post("/probe", headers={"Authorization": "Bearer correct-test-token"})
    assert response.status_code == 200
    assert response.json() == {"status": "passed", "fixture": "iris"}
