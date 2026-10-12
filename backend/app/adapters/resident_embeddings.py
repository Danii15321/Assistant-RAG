import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

from app.adapters.model_snapshot import validate_snapshot
from app.services.embeddings import validate_vectors


class ResidentE5Encoder:
    """Private CPU subprocess, reused between batches and killed on protocol errors."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.process: subprocess.Popen[bytes] | None = None
        self.verified = False

    def close(self) -> None:
        if self.process is not None:
            process, self.process = self.process, None
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()

    def encode(self, texts: list[str], mode: str = "passage") -> list[list[float]]:
        if not 1 <= len(texts) <= 16 or mode not in {"passage", "query"}:
            raise ValueError("embedding_batch")
        payload = json.dumps({"texts": texts, "mode": mode}).encode() + b"\n"
        if len(payload) > 1024 * 1024:
            raise ValueError("embedding_batch")
        if not self.verified:
            validate_snapshot(self.model_path)
            self.verified = True
        starting = self.process is None or self.process.poll() is not None
        try:
            if starting:
                self.close()
                self.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "app.worker.embedding_process",
                        str(self.model_path),
                        "--server",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0,
                )
            result = self.exchange(payload, 90 if starting else 45)
            vectors: list[list[float]] = json.loads(result)
            validate_vectors(vectors, len(texts))
            return vectors
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            self.close()
            raise

    def exchange(self, payload: bytes, timeout: int) -> bytes:
        process = self.process
        assert process is not None and process.stdin is not None and process.stdout is not None
        incoming, outgoing = process.stdout.fileno(), process.stdin.fileno()
        os.set_blocking(incoming, False)
        os.set_blocking(outgoing, False)
        deadline = time.monotonic() + timeout
        sent = 0
        buffer = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("cpu-encoder", timeout)
            readable, writable, _ = select.select(
                [incoming], [outgoing] if sent < len(payload) else [], [], remaining
            )
            if writable:
                sent += os.write(outgoing, payload[sent : sent + 8192])
            if readable:
                block = os.read(incoming, 65536)
                if not block:
                    raise RuntimeError("embedding_unavailable")
                buffer.extend(block)
                if len(buffer) > 512 * 1024:
                    raise ValueError("embedding_batch")
                if b"\n" in buffer:
                    result, tail = bytes(buffer).split(b"\n", 1)
                    if tail:
                        raise ValueError("embedding_protocol")
                    return result
