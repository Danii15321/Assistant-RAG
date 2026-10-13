"""Production-only synthetic account lifecycle and private storage checks."""
import copy
import json
import shlex
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg

from client import Client, QA, REPORTS, save_private

state = json.loads((QA / "production-smoke-state.json").read_text())
assert state["url"] == "https://assistant-rag-three.vercel.app"
account = state["accounts"][1]
assert account["username"].startswith("qualif.b")
env = {}
for line in (QA / "production.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        values = shlex.split(value)
        if values:
            env[key] = values[0]
assert urlparse(env["DATABASE_URL_UNPOOLED"]).hostname.endswith(".neon.tech")
client = Client(state["url"], account)
client.login()
checks = {}
stale = Client(state["url"], account)
for cookie in client.cookies:
    stale.cookies.set_cookie(copy.copy(cookie))
checks["logout"] = client.request("POST", "/api/auth/sign-out")[0] == 200
checks["old_cookie_revoked"] = stale.request("GET", "/api/v1/documents")[0] == 401
client.login()
with psycopg.connect(env["DATABASE_URL_UNPOOLED"]) as connection:
    # Only the synthetic qualification account; no production user's session is touched.
    cursor = connection.execute(
        'UPDATE auth_session SET "expiresAt"=now()-interval \'1 minute\' '
        'WHERE "userId"=(SELECT id FROM auth_user WHERE username=%s)',
        (account["username"],),
    )
    assert cursor.rowcount >= 1
checks["expired_session"] = client.request("GET", "/api/v1/documents")[0] == 401
client.login()
path = QA / "lifecycle-state.json"
progress = json.loads(path.read_text()) if path.exists() else {}
if not progress.get("document"):
    progress["document"] = client.upload("cycle.txt", b"Document fictif de verification du cycle de suppression.", "text/plain")["id"]
    save_private(path, progress)
identifier = progress["document"]
if not progress.get("deleted"):
    client.wait_document(identifier)
    blob_url = "https://" + env["BLOB_HOST"] + "/" + identifier
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(blob_url, timeout=20) as response:
            checks["private_original"] = response.status in (401, 403, 404)
    except urllib.error.HTTPError as error:
        checks["private_original"] = error.code in (401, 403, 404)
    assert checks["private_original"]
    assert client.request("DELETE", "/api/v1/documents/" + identifier)[0] == 202
    checks["immediate_exclusion"] = client.request("GET", "/api/v1/documents/" + identifier)[0] == 404
    checks["repeat_delete"] = client.request("DELETE", "/api/v1/documents/" + identifier)[0] in (202, 404)
    progress.update(deleted=True, checks=checks)
    save_private(path, progress)
else:
    checks.update(progress["checks"])
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    # A normal library visit also retries a missed queue notification.
    client.request("GET", "/api/v1/documents")
    with psycopg.connect(env["DATABASE_URL_UNPOOLED"]) as connection:
        count = connection.execute("SELECT count(*) FROM documents WHERE id=%s", (identifier,)).fetchone()[0]
        chunks = connection.execute("SELECT count(*) FROM index_chunks WHERE document_id=%s", (identifier,)).fetchone()[0]
    if count == 0:
        checks["durable_cleanup"] = chunks == 0
        break
    time.sleep(3)
assert checks.get("durable_cleanup"), "Deletion job has not completed"
report = {"date": datetime.now(timezone.utc).isoformat(), "url": state["url"], "checks": checks,
          "expiry_method": "Expire only the synthetic qualification account's database sessions; preserve its client cookie"}
(REPORTS / "lifecycle-step8.json").write_text(json.dumps(report, indent=2) + "\n")
assert all(checks.values()), checks
print("Lifecycle passed", len(checks), "checks")
