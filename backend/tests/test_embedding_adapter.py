import json
import subprocess
from pathlib import Path

import pytest

from app.adapters.embeddings import E5Encoder


def test_passage_and_query_use_the_same_bounded_offline_encoder(monkeypatch):
    calls = []

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        assert kwargs["timeout"] == 45 and kwargs["stderr"] == subprocess.DEVNULL
        assert json.loads(kwargs["input"]) == ["Texte synthétique"]
        return subprocess.CompletedProcess(arguments, 0, json.dumps([[1] + [0] * 383]).encode())

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("app.adapters.embeddings.validate_snapshot", lambda path: None)
    encoder = E5Encoder(Path("/fixed/model"))
    assert encoder.encode(["Texte synthétique"]) == encoder.encode(["Texte synthétique"], "query")
    assert calls[0][0][-2:] == ["/fixed/model", "passage"]
    assert calls[1][0][-2:] == ["/fixed/model", "query"]
    with pytest.raises(ValueError):
        encoder.encode(["x"] * 17)
    with pytest.raises(ValueError):
        encoder.encode(["x"], "unprefixed")


def test_timeout_and_invalid_vector_never_return_an_embedding(monkeypatch):
    monkeypatch.setattr("app.adapters.embeddings.validate_snapshot", lambda path: None)
    encoder = E5Encoder(Path("/fixed/model"))

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("encoder", 45)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        encoder.encode(["x"])
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, b"[[0.0]]")
    )
    with pytest.raises(ValueError):
        encoder.encode(["x"])
