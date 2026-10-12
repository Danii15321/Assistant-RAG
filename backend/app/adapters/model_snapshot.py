import hashlib
import json
from pathlib import Path

from app.services.embeddings import MODEL_ID, MODEL_REVISION


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def validate_snapshot(path: Path) -> None:
    manifest = json.loads((path / "snapshot-manifest.json").read_text())
    if manifest["model"] != MODEL_ID or manifest["revision"] != MODEL_REVISION:
        raise ValueError("index_incompatible")
    for relative, expected in manifest["files"].items():
        file = (path / relative).resolve()
        if not file.is_relative_to(path.resolve()) or digest_file(file) != expected:
            raise ValueError("index_incompatible")
