"""Materialise the previously qualified immutable E5 snapshot for offline workers."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
SOURCE = Path.home() / ".cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots" / REVISION
DESTINATION = ROOT / ".models/e5"


def main():
    if not SOURCE.is_dir() and '--download' in sys.argv:
        cache = Path.home() / '.cache/huggingface'
        cache.mkdir(parents=True, exist_ok=True)
        DESTINATION.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            'docker', 'compose', 'run', '--rm', '--no-deps',
            '-e', 'HF_HUB_OFFLINE=0', '-e', 'TRANSFORMERS_OFFLINE=0',
            '-v', f'{cache}:/home/app/.cache/huggingface', 'worker', 'python', '-c',
            "from huggingface_hub import snapshot_download; "
            "snapshot_download('intfloat/multilingual-e5-small',"
            f"revision='{REVISION}',allow_patterns=['*.json','*.txt','*.model','model.safetensors'])",
        ], cwd=ROOT, check=True, timeout=600)
    if not SOURCE.is_dir():
        raise RuntimeError("Pinned E5 snapshot absent from local Hugging Face cache; see docs/developpement-local.md")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / 'model.safetensors').is_file() or not (SOURCE / 'tokenizer.json').is_file():
        raise RuntimeError('Incomplete pinned E5 cache')
    files = {}
    for source in SOURCE.rglob("*"):
        if not source.is_file() or source.name == 'README.md':
            continue
        relative = source.relative_to(SOURCE)
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        def digest_file(path):
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                while block := handle.read(1024 * 1024):
                    digest.update(block)
            return digest.hexdigest()
        digest = digest_file(source)
        if not target.exists() or digest_file(target) != digest:
            shutil.copyfile(source, target)
        files[str(relative)] = digest
    (DESTINATION / 'snapshot-manifest.json').write_text(json.dumps({'model': 'intfloat/multilingual-e5-small', 'revision': REVISION, 'files': files}, indent=2) + '\n')
    print(f"Pinned offline E5 snapshot prepared: {len(files)} files")


if __name__ == '__main__':
    main()
