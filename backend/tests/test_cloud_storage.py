import hashlib
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.adapters.blob_storage import BlobStorage
from app.config import Settings


def storage(tmp_path: Path, handler, maximum=100):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return BlobStorage(
        tmp_path,
        "https://frontend.internal",
        "test-secret",
        "unit.private.blob.vercel-storage.com",
        maximum,
        client,
    )


def test_private_blob_hash_and_ephemeral_cleanup(tmp_path):
    identifier = uuid4()

    def handler(request):
        if request.url.host == "frontend.internal":
            assert request.headers["authorization"] == "Bearer test-secret"
            assert request.url.path.endswith(str(identifier))
            return httpx.Response(
                200,
                json={
                    "url": f"https://unit.private.blob.vercel-storage.com/{identifier}?signature=private"
                },
            )
        assert "authorization" not in request.headers
        return httpx.Response(200, content=b"document prive")

    adapter = storage(tmp_path, handler)
    assert adapter.metadata(identifier) == (14, hashlib.sha256(b"document prive").hexdigest())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://unit.private.blob.vercel-storage.com/x",
        "https://evil.example/x",
        "https://unit.private.blob.vercel-storage.com.evil.example/x",
    ],
)
def test_blob_refuses_untrusted_download_destination(tmp_path, url):
    adapter = storage(tmp_path, lambda request: httpx.Response(200, json={"url": url}))
    with pytest.raises(OSError):
        adapter.metadata(uuid4())
    assert list(tmp_path.iterdir()) == []


def test_blob_bounds_body_and_removes_partial_file(tmp_path):
    def handler(request):
        if request.url.host == "frontend.internal":
            return httpx.Response(
                200, json={"url": "https://unit.private.blob.vercel-storage.com/x"}
            )
        return httpx.Response(200, content=b"too many bytes")

    with pytest.raises(OSError):
        storage(tmp_path, handler, maximum=3).metadata(uuid4())
    assert list(tmp_path.iterdir()) == []


def test_cloud_config_rejects_partial_configuration():
    with pytest.raises(ValueError):
        Settings(cloud_runtime=True)


def test_cloud_uses_own_public_origin_without_circular_binding(monkeypatch):
    monkeypatch.setenv("VERCEL_URL", "own-preview.vercel.app")
    config = Settings(
        cloud_runtime=True,
        internal_worker_secret="test-secret",
        blob_host="unit.private.blob.vercel-storage.com",
        database_url_unpooled="postgresql://user:password@db.example/db",
    )
    assert config.frontend_internal_url == "https://own-preview.vercel.app"
    assert config.auth_jwks_url == "https://own-preview.vercel.app/api/auth/jwks"


def test_oidc_is_scoped_to_control_request(tmp_path, monkeypatch):
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "synthetic-oidc")

    def handler(request):
        if request.url.host == "frontend.internal":
            assert request.headers["x-vercel-trusted-oidc-idp-token"] == "synthetic-oidc"
            return httpx.Response(
                200, json={"url": "https://unit.private.blob.vercel-storage.com/x"}
            )
        assert "x-vercel-trusted-oidc-idp-token" not in request.headers
        return httpx.Response(200, content=b"private")

    assert storage(tmp_path, handler).metadata(uuid4())[0] == 7
