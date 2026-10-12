"""Verify private bytes/text survive container replacement, on test data only."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = {**os.environ, "COMPOSE_PROGRESS": "plain"}
SNAPSHOT = r"""
import hashlib,json
from sqlalchemy import text
from app.config import Settings,build_engine
from app.adapters.storage import PrivateStorage
s=Settings()
if not s.database_url or not s.database_url.endswith('/assistant_rag_test'):
    raise RuntimeError('Dedicated local test database required')
e=build_engine(s)
store=PrivateStorage(s.private_storage_path)
result=[]
with e.connect() as c:
    rows=c.execute(text("SELECT id,sha256,unit_count,parser_version FROM documents WHERE stage='extracted' AND state='processing' ORDER BY id")).mappings()
    for row in rows:
        size,digest=store.metadata(row['id'])
        if digest != row['sha256']: raise RuntimeError('Object checksum mismatch')
        units=c.execute(text('SELECT kind,number,text FROM extracted_units WHERE document_id=:id ORDER BY ordinal'),{'id':row['id']}).all()
        result.append({'id':str(row['id']),'size':size,'file_sha256':digest,'unit_count':row['unit_count'],'parser_version':row['parser_version'], 'text_sha256':hashlib.sha256(json.dumps([list(u) for u in units],ensure_ascii=False).encode()).hexdigest()})
e.dispose()
print(json.dumps(result))
"""


def run(arguments, source=None):
    return subprocess.run(["docker", "compose", "--profile", "test", *arguments], cwd=ROOT,
        env=ENVIRONMENT, input=source, text=True, capture_output=True, check=True)


def snapshot():
    output = run(["run", "--rm", "--no-deps", "backend-auth-test", "python", "-"], SNAPSHOT)
    return json.loads(output.stdout)


def main():
    before = snapshot()
    if len(before) < 3:
        raise RuntimeError("Run the real import browser suite before checking persistence")
    try:
        run(["up", "-d", "--no-deps", "--force-recreate", "--wait", "backend-auth-test", "worker-auth-test"])
        after = snapshot()
        if before != after:
            raise RuntimeError("Private extraction changed after service replacement")
        report = {"status": "passed", "environment": "local-test-only", "documents_checked": len(before),
            "file_bytes_and_text_unchanged": True, "containers_replaced": ["backend-auth-test", "worker-auth-test"],
            "cloud_deployment": False}
        (ROOT / "evaluation/reports/import-step3-persistence.json").write_text(json.dumps(report,indent=2)+"\n")
        print(f"Private import persistence verified: {len(before)} test documents")
    finally:
        run(["stop", "frontend-auth-test", "backend-auth-test", "worker-auth-test"])


if __name__ == "__main__":
    main()
