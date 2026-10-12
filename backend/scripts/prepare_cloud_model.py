"""Build-time materialization of the immutable E5 snapshot (no runtime download)."""

import json
from pathlib import Path

from huggingface_hub import snapshot_download

from app.adapters.model_snapshot import digest_file
from app.services.embeddings import MODEL_ID, MODEL_REVISION

root = Path("/opt/models/e5")
snapshot_download(
    MODEL_ID,
    revision=MODEL_REVISION,
    local_dir=root,
    allow_patterns=["*.json", "*.txt", "*.model", "model.safetensors"],
)
files = {
    str(p.relative_to(root)): digest_file(p)
    for p in root.rglob("*")
    if p.is_file() and ".cache" not in p.parts and p.name != "snapshot-manifest.json"
}
(root / "snapshot-manifest.json").write_text(
    json.dumps({"model": MODEL_ID, "revision": MODEL_REVISION, "files": files})
)
