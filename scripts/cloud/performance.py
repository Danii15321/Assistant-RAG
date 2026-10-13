"""Thirty warm searches and thirty generation requests, within real app quotas."""
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
    args = parser.parse_args()
    path = QA / "performance-state.json"
    state = json.loads(path.read_text()) if path.exists() else {"url": args.url, "accounts": [], "last_request": 0}
    assert state["url"] == args.url
    report_path = REPORTS / "performance-step8.json"
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
    # Warmup is reported separately, never included in the thirty warm measurements.
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
    assert all(row["status"] != "reserved" for row in report["answer"]), "Reconcile interrupted request before continuing"
    for index in range(len(report["answer"]), 30):
        until = state["last_request"] + 33
        while time.time() < until:
            time.sleep(min(1, until-time.time()))
        state["last_request"] = time.time()
        row = {"status": "reserved", "account": index // 10}
        report["answer"].append(row)
        persist()
        status, value, elapsed = clients[index // 10].request("POST", "/api/v1/answers", body)
        row.update(status="completed", http_status=status, elapsed_ms=elapsed,
                   state=value.get("state"), provider_called=value.get("provider_called"), server_ms=value.get("elapsed_ms"))
        persist()
        print("generation", index+1, status, elapsed, flush=True)
        assert status == 200, "Stop on failure; counters are never reset"
    for name in ["search", "answer"]:
        values = sorted(r["elapsed_ms"] for r in report[name] if r["http_status"] == 200)
        report[name + "_p95_ms"] = values[math.ceil(0.95 * len(values))-1]
    report["measurement"] = "HTTP round trip from WSL to Vercel fra1; synthetic corpus; three independent users, ten generations each; shared limits unchanged"
    persist()


if __name__ == "__main__":
    main()
