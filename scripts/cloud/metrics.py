"""Read only authenticated, non-sensitive deployment diagnostics."""
import argparse
import json
import shlex
from pathlib import Path

from client import Client, QA

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--environment", choices=["preview", "production"], required=True)
parser.add_argument("--oidc-file")
parser.add_argument("--identity", action="store_true")
args = parser.parse_args()
oidc = None
if args.oidc_file:
    for line in Path(args.oidc_file).read_text().splitlines():
        if line.startswith("VERCEL_OIDC_TOKEN="):
            oidc = shlex.split(line.split("=", 1)[1])[0]
secret = json.loads((QA / (args.environment + "-app-secrets.json")).read_text())["INTERNAL_WORKER_SECRET"]
status, value, elapsed = Client(args.url, {}, oidc).request("GET",
    "/api/internal/metrics" + ("?probe=identity" if args.identity else ""),
    extra_headers={"authorization": "Bearer " + secret})
print(json.dumps({"status": status, "metrics": value, "http_ms": elapsed}))
