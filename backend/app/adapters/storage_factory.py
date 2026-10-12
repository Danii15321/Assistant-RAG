from app.adapters.blob_storage import BlobStorage
from app.adapters.storage import PrivateStorage
from app.config import Settings


def make_storage(settings: Settings) -> PrivateStorage:
    if settings.cloud_runtime:
        assert (
            settings.frontend_internal_url
            and settings.internal_worker_secret
            and settings.blob_host
        )
        return BlobStorage(
            settings.private_storage_path,
            settings.frontend_internal_url,
            settings.internal_worker_secret.get_secret_value(),
            settings.blob_host,
            settings.max_file_bytes,
        )
    return PrivateStorage(settings.private_storage_path)
