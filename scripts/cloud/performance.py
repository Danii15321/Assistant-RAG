"""Bounded latency samples; cloud instance cold starts remain in raw results."""
import argparse
import json
import math
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from client import Client, QA, REPORTS, save_private


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument("--generation-count", type=int, default=30)
    parser.add_argument("--report-suffix", choices=["", "-v4", "-v5", "-v7"], default="")
    args = parser.parse_args()
    assert 1 <= args.generation_count <= 30
    path = QA / "performance-state.json"
    state = json.loads(path.read_text()) if path.exists() else {"url": args.url, "accounts": [], "last_request": 0}
    assert state["url"] == args.url
    report_path = REPORTS / ("performance-step8" + args.report_suffix + ".json")
    previous = json.loads((REPORTS / "performance-step8.json").read_text())["answer"] if args.report_suffix else []
    report = json.loads(report_path.read_text()) if report_path.exists() else {
        "url": args.url, "date": datetime.now(timezone.utc).isoformat(), "search": [], "answer": [], "warmups": []}
    def persist():
        save_private(path, state)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    clients = []
    for index in range(3):
        if len(state["accounts"]) <= index:
            state["accounts"].append({"credentials": {"username": "mesure.t" + secrets.token_hex(5), "password": secrets.token_urlsafe(30)}})
            persist()
        account = state["accounts"][index]
        client = Client(args.url, account["credentials"])
        if account.get("registered"):
            client.login()
        else:
            client.signup()
            account["registered"] = True
            persist()
        if not account.get("document"):
            account["document"] = client.upload("mesure.txt", b"Le projet fictif Oriole est presente le 12 decembre 2026 a Lyon. La demonstration dure vingt minutes.", "text/plain")["id"]
            persist()
        client.wait_document(account["document"])
        clients.append(client)
    body = {"question": "Dans quelle ville est presente le projet Oriole ?", "allow_external_processing": True}
    search_body = {"question": body["question"]}
    # Warmups are reported separately. Subsequent requests may still reach cold instances.
    for i, client in enumerate(clients):
        status, value, elapsed = client.request("POST", "/api/v1/search", search_body)
        report["warmups"].append({"account": i, "http_status": status, "elapsed_ms": elapsed})
        persist()
        assert status == 200 and value["hits"], (status, value)
    for index in range(len(report["search"]), 30):
        status, value, elapsed = clients[index % 3].request("POST", "/api/v1/search", search_body)
        report["search"].append({"http_status": status, "elapsed_ms": elapsed, "server_ms": value.get("elapsed_ms")})
        persist()
        assert status == 200
    if not report.get("concurrent_search"):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda c: c.request("POST", "/api/v1/search", search_body), clients[:2]))
        report["concurrent_search"] = [{"http_status": s, "elapsed_ms": t} for s, _, t in results]
        persist()
        assert all(s == 200 for s, _, _ in results)
    if args.search_only:
        print("Thirty searches and concurrent search completed; no LLM call", flush=True)
        return
    assert all(row["status"] != "reserved" for row in report["answer"]), "Reconcile interrupted request before continuing"
    while sum(r["http_status"] == 200 for r in report["answer"]) < args.generation_count:
        completed = sum(r["http_status"] == 200 for r in report["answer"])
        account_index = next((i for i in range(3) if sum(
            r["account"] == i and r["http_status"] != 429
            for r in previous + report["answer"]
        ) < 10), None)
        assert account_index is not None, "Stop: existing test accounts reached their daily quota"
        # Space from completion: cold encoding can delay the provider reservation
        # and make spacing only the starts exceed the shared two-per-minute cap.
        until = state["last_request"] + 35
        while time.time() < until:
            time.sleep(min(1, until-time.time()))
        state["last_request"] = time.time()
        row = {"status": "reserved", "account": account_index}
        report["answer"].append(row)
        persist()
        status, value, elapsed = clients[account_index].request("POST", "/api/v1/answers", body)
        state["last_request"] = time.time()
        row.update(status="completed", http_status=status, elapsed_ms=elapsed,
                   state=value.get("state"), code=value.get("code"), provider_called=value.get("provider_called"), server_ms=value.get("elapsed_ms"), prompt_version=value.get("prompt_version"))
        persist()
        print("generation", completed+1, status, elapsed, flush=True)
        assert status == 200, "Stop on failure; counters are never reset"
        assert value["provider_called"] and value["state"] == "answered"
        if args.report_suffix:
            assert value["prompt_version"].startswith("grounded-claims" + args.report_suffix)
    for name in ["search", "answer"]:
        values = sorted(r["elapsed_ms"] for r in report[name] if r["http_status"] == 200)
        report[name + "_p95_ms"] = values[math.ceil(0.95 * len(values))-1]
    report["measurement"] = "HTTP round trip from WSL to Vercel fra1; synthetic corpus; three existing test users, maximum ten provider calls each including previous measurements; shared limits unchanged"
    persist()


if __name__ == "__main__":
    main()
