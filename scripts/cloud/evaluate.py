"""Bounded, resumable public-corpus qualification through the deployed API.

Each answer request is reserved on disk before sending. An interrupted request
is never silently repeated. Production application quotas remain unchanged.
"""
import argparse
import hashlib
import json
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone

from client import Client, QA, REPORTS, ROOT, save_private


def corpus(client, state, state_path):
    for fixture in json.loads((ROOT / "evaluation/manifest.json").read_text())["documents"]:
        if fixture["expected"] != "accepted":
            continue
        path = ROOT / "evaluation" / fixture["file"]
        if fixture["id"] not in state["documents"]:
            raw = path.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == fixture["sha256"]
            mime = {".txt": "text/plain", ".pdf": "application/pdf", ".docx":
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[path.suffix]
            doc = client.upload(path.name, raw, mime)
            state["documents"][fixture["id"]] = doc["id"]
            save_private(state_path, state)
        client.wait_document(state["documents"][fixture["id"]])


def recall(client, ids, case, hits):
    annotations = {row["id"]: row for row in json.loads((ROOT / "evaluation/reference_passages.json").read_text())}
    found = []
    for identifier in case["relevant_passage_ids"]:
        annotation = annotations[identifier]
        document = ids[annotation["document_id"]]
        status, units, _ = client.request("GET", "/api/v1/documents/" + document + "/extraction")
        assert status == 200
        kind, number = next(iter(annotation["locator"].items()))
        offset, span = 0, None
        for unit in units:
            if unit["kind"] == kind and unit["number"] == number:
                match = re.search(r"\s+".join(re.escape(w) for w in annotation["text"].split()), unit["text"])
                if match:
                    span = offset + match.start(), offset + match.end()
            offset += len(unit["text"]) + 2
        assert span is not None, identifier
        cursor = span[0]
        for left, right in sorted((h["start_offset"], h["end_offset"]) for h in hits if h["document_id"] == document):
            if left > cursor:
                break
            cursor = max(cursor, right)
        found.append({"reference": identifier, "covered": cursor >= span[1]})
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--split", choices=["development", "final"], required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--report-suffix", default="")
    args = parser.parse_args()
    assert not args.case_id or args.split == "development"
    assert re.fullmatch(r"[a-z0-9-]*", args.report_suffix)
    freeze = REPORTS / "step8-freeze.json"
    if args.split == "final":
        assert freeze.exists(), "Freeze the configuration before final evaluation"
        frozen = json.loads(freeze.read_text())
        assert frozen["questions_sha256"] == hashlib.sha256((ROOT / "evaluation/questions.jsonl").read_bytes()).hexdigest()
    state_path = QA / ("evaluation-" + args.split + ".json")
    if state_path.exists():
        state = json.loads(state_path.read_text())
        assert state["url"] == args.url
    else:
        state = {"url": args.url, "account": {"username": "evaluation.t" + secrets.token_hex(5),
                 "password": secrets.token_urlsafe(30)}, "documents": {}}
        save_private(state_path, state)
    client = Client(args.url, state["account"])
    if state.get("registered"):
        client.login()
    else:
        client.signup()
        state["registered"] = True
        save_private(state_path, state)
    corpus(client, state, state_path)
    cases = [json.loads(line) for line in (ROOT / "evaluation/questions.jsonl").read_text().splitlines()]
    cases = [c for c in cases if c["split"] == args.split and (args.split == "final" or c["id"] in {"Q02", "Q16", "Q21"})]
    if args.case_id:
        cases = [c for c in cases if c["id"] == args.case_id]
        assert cases
    path = REPORTS / ("answers-step8-" + args.split + args.report_suffix + ".json")
    report = json.loads(path.read_text()) if path.exists() else {
        "url": args.url, "split": args.split, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "cases": [], "review_status": "requires-fidelity-review"}
    for case in cases:
        existing = next((r for r in report["cases"] if r["id"] == case["id"]), None)
        if existing:
            assert existing["status"] != "reserved", "Interrupted request requires explicit reconciliation"
            continue
        body = {"question": case["question"], "history": case["history"], "document_ids":
                [state["documents"][d] for d in case["document_ids"]] if case["document_ids"] else None}
        status, search, elapsed = client.request("POST", "/api/v1/search", body)
        assert status == 200, (case["id"], status, search)
        row = {**case, "status": "reserved", "search": search, "search_http_ms": elapsed,
               "recall": recall(client, state["documents"], case, search["hits"])}
        report["cases"].append(row)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        # One request every 33 seconds; never clear or bypass shared production counters.
        until = state.get("last_request", 0) + 33
        while time.time() < until:
            time.sleep(min(1, until - time.time()))
        state["last_request"] = time.time()
        save_private(state_path, state)
        status, answer, elapsed = client.request("POST", "/api/v1/answers", {**body, "allow_external_processing": True})
        row.update(status="completed" if status == 200 else "failed", http_status=status,
                   response=answer, answer_http_ms=elapsed)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(case["id"], status, answer.get("state", answer.get("code")), elapsed, flush=True)
        if status != 200:
            raise RuntimeError("Evaluation stopped on a technical failure; no automatic rerun")


if __name__ == "__main__":
    main()
