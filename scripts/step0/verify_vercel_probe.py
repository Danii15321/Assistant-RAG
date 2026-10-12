"""Vérifier la fixture déployée ; secrets en fichier temporaire privé, jamais argv."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--local", action="store_true")
args = parser.parse_args()
url = args.url.rstrip("/")
parsed = urlparse(url)
assert not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
if args.local:
    assert parsed.hostname in {"127.0.0.1", "localhost"} and parsed.scheme == "http"
else:
    assert parsed.scheme == "https" and parsed.hostname.endswith(".vercel.app")
    project = json.loads((ROOT / ".vercel/project.json").read_text())
    assert project["projectId"] == "prj_YRjALOFSlBmLPqv4n3cJa1CRSV0W"
values = {}
for line in (ROOT / ".env.local").read_text().splitlines():
    name, sep, value = line.partition("=")
    if sep and not name.startswith("#"):
        values[name] = value.strip().strip("\"'")
assert values.get("STEP0_PROBE_TOKEN")
report = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(), "url": url, "target": "local" if args.local else "preview", "scope": "FastAPI → E5 CPU → fixture retrieval → Groq → validated references; no DB, Blob, queue or user accounts", "checks": [], "probes": [], "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["vercel.json", "probes/vercel/app.py", "probes/vercel/Dockerfile.vercel", "probes/vercel/requirements.lock.txt"]}}
with tempfile.TemporaryDirectory(prefix="assistant-rag-probe-") as tmp:
    header = Path(tmp) / "headers"
    header.write_text("Authorization: Bearer " + values["STEP0_PROBE_TOKEN"] + "\n")
    header.chmod(0o600)
    body = Path(tmp) / "response"
    for path, method, authenticated, expected in [("/health", "GET", False, 200), ("/probe", "POST", False, 401), ("/probe", "POST", True, 200), ("/probe", "POST", True, 200)]:
        if args.local:
            command = ["curl", url + path]
        else:
            command = ["npx", "--yes", "vercel@63.1.2", "curl", path, "--deployment", url, "--scope", "danii15321s-projects", "--"]
        command += ["--silent", "--show-error", "--max-time", "120", "--request", method, "--output", str(body), "--write-out", "%{http_code}"]
        if authenticated:
            command += ["--header", "@" + str(header)]
        body.unlink(missing_ok=True)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=150)
        try:
            code = int(result.stdout.strip()[-3:])
        except ValueError:
            code = None
        check = {"path": path, "method": method, "authenticated": authenticated, "http_status": code, "expected_status": expected, "passed": result.returncode == 0 and code == expected}
        report["checks"].append(check)
        if not check["passed"]:
            print(json.dumps(check))
            break
        if authenticated:
            try:
                response = json.loads(body.read_text())
            except ValueError:
                check["passed"] = False
                break
            report["probes"].append(response)
            check["passed"] = response.get("status") == "passed"
            if not check["passed"]:
                break
report["status"] = "passed" if len(report["checks"]) == 4 and all(c["passed"] for c in report["checks"]) else "failed"
destination = ROOT / "evaluation/reports" / ("container-local.json" if args.local else "vercel-step0.json")
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report["status"] == "passed" else 1)
