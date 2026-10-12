import subprocess
import sys
from pathlib import Path

import pytest

from app.adapters.resident_embeddings import ResidentE5Encoder

WORKER = """import json,sys
for line in sys.stdin:
    request=json.loads(line)
    vector=([0,1] if request['mode']=='query' else [1,0])+[0]*382
    print(json.dumps([vector for _ in request['texts']]),flush=True)
"""
REAL_POPEN = subprocess.Popen


def factory(monkeypatch, source=WORKER):
    processes = []

    def create(arguments, **kwargs):
        process = REAL_POPEN([sys.executable, "-c", source], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", create)
    monkeypatch.setattr("app.adapters.resident_embeddings.validate_snapshot", lambda path: None)
    return processes


def test_two_batches_and_query_reuse_one_private_process(monkeypatch):
    processes = factory(monkeypatch)
    encoder = ResidentE5Encoder(Path("/immutable/model"))
    try:
        assert encoder.encode(["Premier lot"])[0][0] == 1
        assert len(encoder.encode(["Deuxième", "Autre passage"])) == 2
        assert encoder.encode(["Question"], "query")[0][1] == 1
        assert len(processes) == 1 and processes[0].poll() is None
    finally:
        encoder.close()
    assert processes[0].poll() is not None


def test_timeout_kills_child_and_next_batch_starts_a_fresh_process(monkeypatch):
    processes = factory(monkeypatch, "import time; time.sleep(10)")
    encoder = ResidentE5Encoder(Path("/immutable/model"))
    exchange = encoder.exchange
    monkeypatch.setattr(encoder, "exchange", lambda payload, timeout: exchange(payload, 1))
    with pytest.raises(subprocess.TimeoutExpired):
        encoder.encode(["lot"])
    assert processes[0].poll() is not None and encoder.process is None
    processes = factory(monkeypatch)
    assert encoder.encode(["reprise"])[0][0] == 1
    encoder.close()
    assert len(processes) == 1


def test_bad_protocol_and_invalid_batch_cannot_return_vectors(monkeypatch):
    processes = factory(
        monkeypatch, "import sys; sys.stdin.readline(); print('[[0.0]]',flush=True)"
    )
    encoder = ResidentE5Encoder(Path("/immutable/model"))
    with pytest.raises(ValueError):
        encoder.encode(["x"] * 17)
    assert processes == []
    with pytest.raises(ValueError):
        encoder.encode(["x"])
    assert encoder.process is None and processes[0].poll() is not None
