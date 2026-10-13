"""Summarize recorded cloud calls without making or repeating provider requests."""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[2] / "evaluation/reports"


def summary(values):
    ordered = sorted(values)
    return {"count": len(ordered), "p95_ms": ordered[math.ceil(.95 * len(ordered)) - 1],
            "min_ms": ordered[0], "max_ms": ordered[-1]} if ordered else {"count": 0}


def main():
    calls, failures = [], []
    for path in sorted(REPORTS.glob("answers-step8*.json")):
        for row in json.loads(path.read_text())["cases"]:
            answer = row.get("response", {})
            if row.get("http_status") != 200:
                failures.append({"report": path.name, "case": row["id"],
                                 "status": row["status"], "code": answer.get("code")})
            elif answer.get("provider_called"):
                calls.append({"report": path.name, "case": row["id"],
                              "version": answer["prompt_version"],
                              "state": answer["state"], "http_ms": row["answer_http_ms"]})
    for path in sorted(REPORTS.glob("performance-step8*.json")):
        for index, row in enumerate(json.loads(path.read_text()).get("answer", [])):
            if row.get("http_status") != 200:
                failures.append({"report": path.name, "case": index, "code": row.get("code")})
            elif row.get("provider_called"):
                calls.append({"report": path.name, "case": index,
                              "version": row.get("prompt_version", "not-recorded-in-initial-benchmark"),
                              "state": row["state"], "http_ms": row["elapsed_ms"]})
    groups = defaultdict(list)
    for call in calls:
        groups[call["version"]].append(call["http_ms"])
    searches = {}
    for path in sorted(REPORTS.glob("performance-step8*.json")):
        raw = json.loads(path.read_text())
        searches[path.name] = {**summary([r["elapsed_ms"] for r in raw["search"]]),
                               "concurrent": raw.get("concurrent_search", [])}
    report = {
        "date": datetime.now(timezone.utc).isoformat(),
        "configuration": "Vercel fra1, backend 2048 MiB / 1 CPU, E5 small fixed revision, Groq gpt-oss-120b, input 2500 + completion 600 tokens",
        "measurement": "HTTP round trip WSL -> public Vercel; synthetic corpora; sequential provider calls with ordinary shared quotas",
        "generation_successes": summary([c["http_ms"] for c in calls]),
        "generation_by_prompt": {k: summary(v) for k, v in groups.items()},
        "generation_failures": failures, "calls": calls, "search_runs": searches,
        "limitations": [
            "Cross-version qualification aggregate, not 30 requests on the final prompt alone.",
            "Cold requests are retained: per-request instance/model-loaded state was not instrumented.",
            "Success latency includes explicit LLM abstentions; failures remain separate and are never successful abstentions.",
            "Browser exchanges use UI timing and are reported separately; private local diagnostics are excluded.",
            "Initial benchmark did not record prompt_version; it is explicitly unknown here.",
        ],
    }
    (REPORTS / "latency-step8.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"generation": report["generation_successes"], "search": searches}, indent=2))


if __name__ == "__main__":
    main()
