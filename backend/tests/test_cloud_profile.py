from contextlib import contextmanager
from threading import Lock
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.internal import router
from app.models.document import DocumentError
from app.worker.cloud import CloudWorker


def test_embedding_profile_uses_the_shared_cpu_guard_and_releases_on_failure(monkeypatch):
    calls = []

    @contextmanager
    def guard(engine):
        calls.append("lock")
        yield True

    class Encoder:
        process = None

        def encode(self, texts, mode):
            calls.append((texts, mode))
            if len(calls) == 3:
                raise RuntimeError("synthetic failure")

    monkeypatch.setattr("app.worker.cloud.cpu_guard", guard)
    worker = CloudWorker.__new__(CloudWorker)
    worker.lock, worker.engine = Lock(), None
    worker.indexer = SimpleNamespace(encoder=Encoder())
    with pytest.raises(RuntimeError):
        worker.profile_embeddings()
    assert not worker.lock.locked()
    assert calls == [
        "lock",
        (["Qualification E5 sans document utilisateur."], "query"),
        (["Qualification E5 sans document utilisateur."], "query"),
    ]
    worker.lock.acquire()
    with pytest.raises(DocumentError, match="generation_busy"):
        worker.profile_embeddings()
    worker.lock.release()


def test_embedding_probe_is_internal_only_and_does_not_accept_document_text():
    calls = []
    app = FastAPI()
    app.include_router(router)
    app.state.settings = SimpleNamespace(
        cloud_runtime=True, internal_worker_secret=SecretStr("test")
    )
    app.state.cloud_worker = SimpleNamespace(
        indexer=SimpleNamespace(encoder=SimpleNamespace(process=None)),
        profile_embeddings=lambda: (
            calls.append(True) or {"initially_loaded": False, "first_ms": 1, "warm_ms": 1}
        ),
    )
    with TestClient(app) as client:
        assert client.get("/internal/metrics?probe=embedding").status_code == 404
        assert calls == []
        response = client.get(
            "/internal/metrics?probe=embedding", headers={"authorization": "Bearer test"}
        )
        assert response.status_code == 200
        assert response.json()["embedding"]["initially_loaded"] is False
        assert response.json()["resident_mib"] > 0
        assert calls == [True]
