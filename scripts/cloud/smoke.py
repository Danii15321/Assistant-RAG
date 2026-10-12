"""Cloud qualification: auth, direct private upload and E5; no LLM call."""
import argparse
import hashlib
import json
import secrets
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path

from client import Client, QA, REPORTS, ROOT, save_private

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--environment", choices=["preview", "production"], required=True)
parser.add_argument("--oidc-file")
args = parser.parse_args()
oidc = None
if args.oidc_file:
    for line in Path(args.oidc_file).read_text().splitlines():
        if line.startswith("VERCEL_OIDC_TOKEN="):
            oidc = shlex.split(line.split("=", 1)[1])[0]
state_path = QA / (args.environment + "-smoke-state.json")
if state_path.exists():
    state = json.loads(state_path.read_text())
    assert state["url"] == args.url
else:
    suffix = secrets.token_hex(5)
    state = {"url": args.url, "accounts": [
        {"username": "qualif.a" + suffix, "password": secrets.token_urlsafe(30)},
        {"username": "qualif.b" + suffix, "password": secrets.token_urlsafe(30)}], "documents": {}}
    save_private(state_path, state)
clients = [Client(args.url, account, oidc) for account in state["accounts"]]
for i, client in enumerate(clients):
    key = "registered" + str(i)
    if state.get(key):
        client.login()
    else:
        client.signup()
        state[key] = True
        save_private(state_path, state)
alice, bob = clients
checks = {}
checks["health"] = alice.request("GET", "/api/v1/health")[0] == 200
checks["wrong_origin"] = alice.request("POST", "/api/v1/conversations", origin="https://other.example")[0] == 403
manifest = json.loads((ROOT / "evaluation/manifest.json").read_text())
for fixture in manifest["documents"]:
    if fixture["expected"] != "accepted":
        continue
    path = ROOT / "evaluation" / fixture["file"]
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == fixture["sha256"]
    if fixture["id"] not in state["documents"]:
        start = time.monotonic()
        mime = {".txt": "text/plain", ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[path.suffix]
        document = alice.upload(path.name, raw, mime)
        state["documents"][fixture["id"]] = document["id"]
        save_private(state_path, state)
        print("uploaded", path.name, flush=True)
        result = alice.wait_document(document["id"])
        state.setdefault("import_ms", {})[fixture["id"]] = round(1000 * (time.monotonic() - start), 2)
        save_private(state_path, state)
    else:
        result = alice.wait_document(state["documents"][fixture["id"]])
    checks["indexed_" + fixture["id"]] = result["chunk_count"] > 0 and result["embedded_count"] == result["chunk_count"]
    identifier = result["id"]
    for route, method in [("", "GET"), ("/extraction", "GET"), ("/passages", "GET"), ("/retry", "POST"), ("", "DELETE")]:
        checks["isolation_" + fixture["id"] + method + route] = bob.request(method, "/api/v1/documents/" + identifier + route)[0] == 404
    checks["selection_isolation_" + fixture["id"]] = bob.request("POST", "/api/v1/search", {"question": "Iris", "document_ids": [identifier]})[0] == 404
checks["empty_other_library"] = bob.request("GET", "/api/v1/documents")[1] == []
if not state.get("twenty_mib"):
    raw = b"Qualification vingt Mio.\n"
    raw += b" " * (20 * 1024 * 1024 - len(raw))
    result = alice.upload("vingt-mio.txt", raw, "text/plain")
    state["twenty_mib"] = result["id"]
    save_private(state_path, state)
result = alice.wait_document(state["twenty_mib"])
checks["direct_twenty_mib"] = result["size_bytes"] == 20 * 1024 * 1024
checks["too_large"] = alice.request("POST", "/api/v1/documents/uploads", {"filename": "too-large.txt", "size_bytes": 20*1024*1024+1, "content_type": "text/plain"})[0] == 413
for filename in ["scan.pdf", "corrompu.pdf"]:
    if filename not in state["documents"]:
        document = alice.upload(filename, (ROOT / "evaluation/corpus" / filename).read_bytes(), "application/pdf")
        state["documents"][filename] = document["id"]
        save_private(state_path, state)
    result = alice.wait_document(state["documents"][filename], "failed")
    checks["reject_" + filename] = result["state"] == "failed"
checks["anonymous_internal"] = Client(args.url, {}, oidc).request("POST", "/api/internal/blob/reconcile", {"live": []})[0] == 404
checks["signout"] = alice.request("POST", "/api/auth/sign-out")[0] == 200
checks["session_revoked"] = alice.request("GET", "/api/v1/documents")[0] == 401
report = {"date": datetime.now(timezone.utc).isoformat(), "environment": args.environment, "url": args.url,
    "checks": checks, "import_ms": state.get("import_ms"), "real_llm_calls": 0,
    "status": "passed" if all(checks.values()) else "failed"}
(REPORTS / ("cloud-step8-" + args.environment + ".json")).write_text(json.dumps(report, indent=2) + "\n")
print(report["status"], len(checks), "checks", flush=True)
assert all(checks.values()), [key for key, value in checks.items() if not value]
