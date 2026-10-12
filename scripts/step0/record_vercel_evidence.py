"""Consigner uniquement les métadonnées non secrètes du déploiement qualifié."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "prj_YRjALOFSlBmLPqv4n3cJa1CRSV0W"
SCOPE = "danii15321s-projects"
DEPLOYMENT = "dpl_CJPLW6bD9ExEQ4GD8ahZjtSdPLZt"
linked = json.loads((ROOT / ".vercel/project.json").read_text())
assert linked["projectId"] == PROJECT
assert linked["orgId"] == "team_6581oKjjxVSAFKPlCJXuEd8t"


def read_cli(arguments):
    result = subprocess.run(
        ["npx", "--yes", "vercel@63.1.2", *arguments, "--scope", SCOPE, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=60, check=True,
    )
    return json.loads(result.stdout)


deployment = read_cli(["inspect", DEPLOYMENT])
registry = read_cli(["vcr", "image", "ls", "qualification", "--project", PROJECT])
images = registry["images"]
image = next(i for i in images if DEPLOYMENT in i["tags"])
assert image["status"] == "ready"
report = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "project": {"id": PROJECT, "name": "assistant-rag", "scope": SCOPE, "plan": "hobby"},
    "deployment": {key: deployment[key] for key in ["id", "url", "target", "readyState", "createdAt", "regions"] if key in deployment},
    "image": {key: image[key] for key in ["manifestDigest", "platform", "arch", "sizeInBytes", "status", "createdAt", "tags"]},
    "registry_image_count_observed": len(images),
    "registry_bytes_observed": sum(i["sizeInBytes"] for i in images),
    "groq_billing": {"plan": "Free", "evidence": "Owner explicitly confirmed Settings → Billing shows Free on 2026-10-11", "api_exposes_plan": False},
    "limits": "Fixed synthetic fixture only; no DB, Blob, queue, user accounts or infrastructure invoice certification",
}
assert report["deployment"]["id"] == DEPLOYMENT
assert report["deployment"].get("readyState") == "READY"
destination = ROOT / "evaluation/reports/vercel-deployment-step0.json"
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
