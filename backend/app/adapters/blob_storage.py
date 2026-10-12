"""Private Blob originals; only bounded, short-lived parser files touch /tmp."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.adapters.storage import PrivateStorage


class BlobStorage(PrivateStorage):
    def __init__(
        self,
        root: Path,
        bridge: str,
        secret: str,
        host: str,
        maximum: int,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(root)
        self.bridge, self.secret, self.host, self.maximum = bridge, secret, host, maximum
        self.client = client

    @contextmanager
    def http(self) -> Iterator[httpx.Client]:
        if self.client is not None:
            yield self.client
        else:
            with httpx.Client(timeout=40, follow_redirects=False, trust_env=False) as client:
                yield client

    def control(self, method: str, path: str, body: object = None) -> httpx.Response:
        try:
            with self.http() as client:
                result = client.request(
                    method,
                    self.bridge.rstrip("/") + "/api/internal/blob/" + path,
                    headers={"authorization": "Bearer " + self.secret},
                    json=body,
                )
            result.raise_for_status()
            return result
        except httpx.HTTPError:
            raise OSError("storage_unavailable") from None

    @contextmanager
    def open_file(self, document_id: UUID) -> Iterator[Path]:
        temporary = self.temporary()
        try:
            payload = self.control("GET", str(document_id)).json()
            url = payload["url"]
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname != self.host or parsed.username:
                raise OSError("storage_unavailable")
            size = 0
            with self.http() as client, client.stream("GET", url) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_bytes(65536):
                        size += len(chunk)
                        if size > self.maximum:
                            raise OSError("storage_limit")
                        output.write(chunk)
            yield temporary
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise OSError("storage_unavailable") from None
        finally:
            temporary.unlink(missing_ok=True)

    def delete(self, document_id: UUID) -> None:
        self.control("DELETE", str(document_id))

    def collect_orphans(self, live_ids: set[UUID], grace_seconds: int = 3600) -> int:
        result = self.control("POST", "reconcile", {"live": [str(i) for i in live_ids]})
        return int(result.json()["removed"])
