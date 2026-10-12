"""Local private adapter. Object keys are server-generated UUIDs, never filenames."""

import hashlib
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4


class PrivateStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)

    def path(self, document_id: UUID) -> Path:
        return self.root / str(document_id)

    @contextmanager
    def open_file(self, document_id: UUID) -> Iterator[Path]:
        yield self.path(document_id)

    def temporary(self) -> Path:
        path = self.root / (str(uuid4()) + ".part")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        return path

    def commit(self, temporary: Path, document_id: UUID) -> None:
        # Atomic, exclusive publication; a repeated upload cannot overwrite an object.
        os.link(temporary, self.path(document_id))

    def delete(self, document_id: UUID) -> None:
        self.path(document_id).unlink(missing_ok=True)

    def metadata(self, document_id: UUID) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        with self.open_file(document_id) as path, path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(part)
                digest.update(part)
        return size, digest.hexdigest()

    def collect_orphans(self, live_ids: set[UUID], grace_seconds: int = 3600) -> int:
        removed = 0
        for path in self.root.iterdir():
            if not path.is_file() or time.time() - path.stat().st_mtime < grace_seconds:
                continue
            try:
                live = UUID(path.name) in live_ids
            except ValueError:
                live = False
            if path.suffix == ".part" or not live:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
