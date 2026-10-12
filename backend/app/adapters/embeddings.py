import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.adapters.model_snapshot import validate_snapshot
from app.services.embeddings import validate_vectors


class E5Tokenizer:
    def __init__(self, model_path: Path) -> None:
        from tokenizers import Tokenizer

        self.tokenizer: Any = Tokenizer.from_file(str(model_path / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [
            (int(start), int(end))
            for start, end in self.tokenizer.encode(text, add_special_tokens=False).offsets
        ]


class E5Encoder:
    """CPU subprocess: a killed or slow batch never publishes a partial index."""

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.verified = False

    def encode(self, texts: list[str], mode: str = "passage") -> list[list[float]]:
        if not 1 <= len(texts) <= 16 or mode not in {"passage", "query"}:
            raise ValueError("embedding_batch")
        if not self.verified:
            validate_snapshot(self.model_path)
            self.verified = True
        result = subprocess.run(
            [sys.executable, "-m", "app.worker.embedding_process", str(self.model_path), mode],
            input=json.dumps(texts).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=45,
            check=False,
        )
        if result.returncode or len(result.stdout) > 512 * 1024:
            raise RuntimeError("embedding_unavailable")
        payload: list[list[float]] = json.loads(result.stdout)
        validate_vectors(payload, len(texts))
        return payload
