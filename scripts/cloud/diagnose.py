"""One reserved synthetic development diagnostic using the production quota ledger."""
import json
import argparse
import shlex
import time
from pathlib import Path

from sqlalchemy import text

from app.adapters.groq import GroqProvider
from app.config import Settings, build_engine
from app.models.document import DocumentError
from app.models.search import SearchHit, SearchRequest
from app.repositories.generation import GenerationRepository
from app.repositories.search import SearchRepository
from app.services.generation import build_context, validate_answer
from client import Client, QA, REPORTS, save_private

parser = argparse.ArgumentParser()
parser.add_argument("--run", choices=["v5", "followup-v5", "followup-v5-b"], required=True)
args = parser.parse_args()
case_id = "Iris-followup" if args.run.startswith("followup") else "Q16"
marker = QA / ("diagnostic-" + args.run + ".json")
assert not marker.exists(), "One-call diagnostic already reserved"
env = {}
for line in (QA / "production.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        key, value = line.split("=", 1)
        values = shlex.split(value)
        if values:
            env[key.lower()] = values[0]
state = json.loads((QA / "evaluation-development.json").read_text())
if args.run.startswith("followup-v5"):
    state = json.loads((QA / "diagnostic-followup-input.json").read_text())
assert state["account"]["username"].startswith(("evaluation.t", "qualif.a"))
env.pop("groq_api_key", None)  # Vercel does not export sensitive keys.
settings = Settings(**env)
engine = build_engine(settings)
assert engine is not None
with engine.connect() as c:
    owner, session = c.execute(text(
        'SELECT u.id,s.id FROM users u JOIN auth_user a ON a.id=u.auth_user_id '
        'JOIN auth_session s ON s."userId"=a.id WHERE a.username=:username '
        'AND s."expiresAt">now() ORDER BY s."createdAt" DESC LIMIT 1'
    ), {"username": state["account"]["username"]}).one()
case = next(c for c in json.loads((REPORTS / "answers-step8-development-v4.json").read_text())["cases"] if c["id"] == "Q16")
if args.run.startswith("followup-v5"):
    case = state
body = SearchRequest(question=case["question"], history=case["history"])
context = build_context(body, [SearchHit.model_validate(h) for h in case["search"]["hits"]])
repository = GenerationRepository(engine)
sources = SearchRepository(engine)
sources.verify_hits(owner, context.sources)
save_private(marker, {"state": "reserved", "case": case_id, "shared_production_quotas": True})
lease, attempt = repository.acquire(owner, session, 3100)
completion = None
outcome = "failed"
try:
    completion = GroqProvider(settings).generate(context.messages, time.monotonic() + 55)
    sources.verify_hits(owner, context.sources)
    raw = json.loads(completion.content)
    save_private(marker, {"state": "received", "case": case_id, "raw": raw,
                          "context": context.messages, "shared_production_quotas": True})
    try:
        result = validate_answer(completion.content, context.sources)
        outcome = result.state
        print("Diagnostic validation:", outcome)
    except DocumentError as error:
        print("Diagnostic validation:", error.code)
    print(json.dumps(raw, ensure_ascii=False))
finally:
    repository.finish_attempt(attempt, outcome, completion.prompt_tokens if completion else None,
                              completion.completion_tokens if completion else None)
    repository.release(lease)
    engine.dispose()
