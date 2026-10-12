"""Configurer les deux secrets du prototype en Preview, sans les exposer."""
import json
import secrets
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
project = json.loads((root / ".vercel/project.json").read_text())
assert project["projectId"] == "prj_YRjALOFSlBmLPqv4n3cJa1CRSV0W"
assert project["orgId"] == "team_6581oKjjxVSAFKPlCJXuEd8t"
path = root / ".env.local"
values = {}
for line in path.read_text().splitlines():
    name, sep, value = line.partition("=")
    if sep and not name.startswith("#"):
        values[name] = value.strip().strip("\"'")
assert values.get("GROQ_API_KEY"), "missing local Groq key"
if not values.get("STEP0_PROBE_TOKEN"):
    values["STEP0_PROBE_TOKEN"] = secrets.token_urlsafe(32)
    with path.open("a") as handle:
        handle.write("\nSTEP0_PROBE_TOKEN=" + values["STEP0_PROBE_TOKEN"] + "\n")
path.chmod(0o600)
for name in ["GROQ_API_KEY", "STEP0_PROBE_TOKEN"]:
    result = subprocess.run(
        ["npx", "--yes", "vercel@63.1.2", "env", "add", name, "preview", "--type", "secret", "--yes", "--scope", "danii15321s-projects", "--project", "assistant-rag"],
        cwd=root, input=values[name], text=True, capture_output=True,
    )
    print(json.dumps({"variable": name, "environment": "preview", "type": "secret", "exit_code": result.returncode}))
    if result.returncode:
        message = result.stdout + result.stderr
        for sensitive in values.values():
            if sensitive:
                message = message.replace(sensitive, "[REDACTED]")
        print(message[-1500:])
        raise SystemExit(result.returncode)
