import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.health import get_readiness
from app.config import Settings
from app.main import create_app
from app.services.readiness import ReadinessService


class StubDatabase:
    def __init__(self, ready: bool = True, error: Exception | None = None) -> None:
        self.ready = ready
        self.error = error

    def is_ready(self) -> bool:
        if self.error:
            raise self.error
        return self.ready


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_readiness] = lambda: ReadinessService(StubDatabase())
    with TestClient(app) as test_client:
        yield test_client


def test_liveness_does_not_require_database(client: TestClient) -> None:
    client.app.dependency_overrides[get_readiness] = lambda: ReadinessService(  # type: ignore[attr-defined]
        StubDatabase(error=RuntimeError("database is offline"))
    )
    assert client.get("/health").json() == {"status": "ok"}


def test_unconfigured_application_is_alive_but_not_ready() -> None:
    with TestClient(create_app(Settings(database_url=None))) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 503


def test_readiness_success_has_no_infrastructure_details(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_unmigrated_database_is_not_ready(client: TestClient) -> None:
    client.app.dependency_overrides[get_readiness] = lambda: ReadinessService(  # type: ignore[attr-defined]
        StubDatabase(ready=False)
    )
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_database_errors_are_sanitized(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "postgresql://private-user:private-password@private-host/private-db"
    client.app.dependency_overrides[get_readiness] = lambda: ReadinessService(  # type: ignore[attr-defined]
        StubDatabase(error=RuntimeError(secret))
    )
    with caplog.at_level(logging.WARNING):
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert secret not in response.text
    assert secret not in caplog.text
    assert "private-password" not in caplog.text
