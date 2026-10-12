"""At most three actual Groq calls on public development fixtures, no automatic retries."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.adapters.groq import Completion, GroqProvider, ProviderError
from app.models.answer import AnswerRequest
from app.models.document import DocumentError
from app.repositories.generation import GenerationRepository
from app.repositories.query_jobs import QueryJobRepository
from app.repositories.search import SearchRepository
from app.services.answers import AnswerService
from app.services.generation import PROMPT_VERSION, build_context
from app.services.search import SearchService
from app.worker.query import QueryWorker
from scripts.evaluation_corpus import evaluation_corpus


class InlineQueryJobs(QueryJobRepository):
    def __init__(self, engine, encoder):
        super().__init__(engine)
        self.worker = QueryWorker(self, encoder)

    def submit(self, owner, session, question):
        id = super().submit(owner, session, question)
        if not self.worker.run_once():
            raise RuntimeError("Real query job was not claimed")
        return id


class ThreeCalls:
    def __init__(self, provider, revalidate_retained=False):
        self.provider = provider
        self.calls = 0
        self.ledger_path = Path("/data/private/step6-call-ledger.json")
        self.ledger = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else []
        self.case_id = ""
        self.revalidate_retained = revalidate_retained
        self.reused = []

    def ready(self):
        return self.provider.ready()

    def generate(self, messages, deadline):
        if self.revalidate_retained:
            retained = next(
                (
                    entry
                    for entry in self.ledger
                    if entry["case_id"] == self.case_id and entry["status"] == "completed"
                ),
                None,
            )
            if retained:
                self.reused.append(self.case_id)
                return Completion(
                    retained["content"], retained["prompt_tokens"], retained["completion_tokens"]
                )
        if self.calls >= 3 or len(self.ledger) >= 3:
            raise ProviderError("qualification_limit")
        self.calls += 1
        entry = {"case_id": self.case_id, "status": "reserved"}
        self.ledger.append(entry)
        self.ledger_path.write_text(json.dumps(self.ledger, ensure_ascii=False, indent=2))
        try:
            result = self.provider.generate(messages, deadline)
            entry.update(
                {
                    "status": "completed",
                    "content": result.content,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                }
            )
            return result
        except ProviderError as error:
            # No retries in the explicitly bounded real qualification.
            entry.update({"status": "failed", "code": error.code})
            raise ProviderError(error.code, False, error.retry_after) from None
        finally:
            self.ledger_path.write_text(json.dumps(self.ledger, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", required=True)
    parser.add_argument("--revalidate-retained", action="store_true")
    arguments = parser.parse_args()
    cases = [
        json.loads(line) for line in Path("/evaluation/questions.jsonl").read_text().splitlines()
    ]
    cases = [q for q in cases if q["split"] == "development" and q["id"] in {"Q02", "Q16", "Q21"}]
    assert len(cases) == 3
    with evaluation_corpus() as (settings, engine, owner, session, indexer, ids):
        provider = ThreeCalls(GroqProvider(settings), arguments.revalidate_retained)
        assert provider.ready()
        search_repo = SearchRepository(engine)
        search = SearchService(
            search_repo, InlineQueryJobs(engine, indexer.encoder), settings.search_threshold
        )

        def active():
            with engine.connect() as c:
                return bool(
                    c.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM auth_session "
                            'WHERE id=:id AND "expiresAt">now())'
                        ),
                        {"id": session},
                    ).scalar_one()
                )

        quota = GenerationRepository(engine)
        service = AnswerService(search, quota, provider, search_repo.verify_hits)
        requests = []
        for case in cases:
            body = AnswerRequest(
                question=case["question"],
                history=case["history"],
                document_ids=[ids[n] for n in case["document_ids"]]
                if case["document_ids"] is not None
                else None,
                allow_external_processing=True,
            )
            found = search.execute(owner, session, body, active)
            if found.hits:
                build_context(body, found.hits)
            requests.append((case, body))
        rows = []
        for case, body in requests:
            # The third external request waits for the application's 2/minute budget.
            with engine.connect() as c:
                wait = c.execute(
                    text(
                        "SELECT greatest(0,61-extract(epoch FROM "
                        "now()-min(created_at))) FROM "
                        "generation_attempts WHERE "
                        "created_at>now()-interval '1 minute'"
                    )
                ).scalar_one()
                count = c.execute(
                    text(
                        "SELECT count(*) FROM generation_attempts "
                        "WHERE created_at>now()-interval '1 minute'"
                    )
                ).scalar_one()
            if count >= 2:
                until = time.monotonic() + float(wait or 0)
                while time.monotonic() < until:
                    time.sleep(min(1, until - time.monotonic()))
            provider.case_id = case["id"]
            try:
                result = service.execute(owner, session, body, active)
            except DocumentError as error:
                rows.append({"id": case["id"], "state": "failed", "code": error.code})
                break
            rows.append(
                {
                    "id": case["id"],
                    "expected_state": case["expected_state"],
                    "expected_elements": case["expected_elements"],
                    **result.model_dump(mode="json"),
                }
            )
        with engine.connect() as c:
            usage = [
                dict(row)
                for row in c.execute(
                    text(
                        "SELECT "
                        "prompt_tokens,completion_tokens,outcome FROM "
                        "generation_attempts WHERE owner_id=:owner "
                        "ORDER BY created_at"
                    ),
                    {"owner": owner},
                ).mappings()
            ]
        report = {
            "status": "failed"
            if any(r["state"] == "failed" for r in rows)
            else "requires-human-fidelity-review",
            "synthetic_call_ledger": provider.ledger,
            "retained_real_replies_revalidated": provider.reused,
            "known_actual_calls_in_ledger": len(provider.ledger),
            "earlier_failed_run_calls_upper_bound": 3,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_cases": rows,
            "final_cases_evaluated": 0,
            "actual_groq_calls": provider.calls,
            "usage": usage,
            "prompt_version": PROMPT_VERSION,
            "cost_eur": 0,
            "cloud_deployment": False,
            "scope": (
                "real E5/private SQL/query jobs + answer service + actual Groq; "
                "JWT/browser separately qualified with HTTP simulation"
            ),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
