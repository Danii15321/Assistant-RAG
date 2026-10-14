from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import text

from app.models.document import DocumentError
from app.repositories.openai_budget import OpenAIBudgetRepository

pytest_plugins = ["test_documents"]
pytestmark = pytest.mark.integration


def test_concurrent_calls_cannot_exceed_one_dollar_and_restart_keeps_total(database):
    engine, config = database
    command.upgrade(config, "head")

    def reserve(_):
        try:
            OpenAIBudgetRepository(engine).reserve("gpt-6.1-sol")
            return True
        except DocumentError as error:
            assert error.code == "openai_budget_exhausted"
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 8
    assert OpenAIBudgetRepository(engine).remaining_microusd() == 40_000
    for _ in range(4):
        OpenAIBudgetRepository(engine).reserve("gpt-6-luna")
    with pytest.raises(DocumentError, match="openai_budget_exhausted"):
        OpenAIBudgetRepository(engine).reserve("gpt-6-luna")
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT sum(reserved_microusd) FROM openai_trial_attempts")).scalar_one()
            == 1_000_000
        )
    command.downgrade(config, "0008_cloud_wakeups")
    command.upgrade(config, "head")
    assert OpenAIBudgetRepository(engine).remaining_microusd() == 0


def test_model_is_part_of_idempotency_but_legacy_groq_is_compatible(database):
    import hashlib
    import json
    from uuid import uuid4

    from app.models.conversation import MessageRequest

    body = MessageRequest(request_id=uuid4(), question="Une question ?")
    legacy = body.model_dump(mode="json", exclude={"request_id", "model"})
    from app.repositories.conversations import request_fingerprint

    assert (
        request_fingerprint(body)
        == hashlib.sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest()
    )
    assert request_fingerprint(body) != request_fingerprint(
        body.model_copy(update={"model": "gpt-6-luna"})
    )


@pytest.mark.usefixtures("context")
def test_selected_model_persists_and_replay_cannot_change_it(context):
    from test_conversations_database import response, start

    repo, conversation, body = start(context)
    owner = context[1][0]
    body = body.model_copy(update={"model": "gpt-6-luna"})
    exchange, created = repo.begin(owner, conversation.id, body)
    assert created and exchange.model == "gpt-6-luna"
    _, answer = response(context)
    answer.model = "gpt-6-luna"
    repo.complete(owner, conversation.id, exchange.id, answer, lambda: True)
    replay, created = repo.begin(owner, conversation.id, body)
    assert not created and replay.model == "gpt-6-luna"
    assert replay.answer["model"] == "gpt-6-luna"
    with pytest.raises(DocumentError, match="request_conflict"):
        repo.begin(owner, conversation.id, body.model_copy(update={"model": "groq"}))


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
def test_openai_answer_runs_through_real_daily_and_paid_budgets(
    context, tmp_path, monkeypatch, model
):
    import json
    from datetime import date
    from types import SimpleNamespace

    import httpx
    from test_answers import hit

    from app.adapters.openai import OpenAIProvider
    from app.config import Settings
    from app.models.answer import AnswerRequest
    from app.repositories.generation import GenerationRepository
    from app.services.answers import AnswerService

    monkeypatch.setattr("app.adapters.openai.PRICING_VALID_UNTIL", date.max)
    engine, owners, *_ = context
    key = tmp_path / "key"
    key.write_text("synthetic-key")
    budget = OpenAIBudgetRepository(engine)
    calls = []

    def respond(request):
        calls.append(1)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "state": "answered",
                                    "claims": [
                                        {
                                            "text": "Le lancement a lieu à Lyon.",
                                            "evidence": [{"source_id": "S1", "excerpt_id": "E1"}],
                                        }
                                    ],
                                }
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 500, "completion_tokens": 100},
            },
        )

    provider = OpenAIProvider(
        Settings(openai_local_enabled=True, openai_api_key_file=key),
        model,
        budget,
        httpx.MockTransport(respond),
    )
    search = SimpleNamespace(execute=lambda *args: SimpleNamespace(hits=[hit()]))
    service = AnswerService(search, GenerationRepository(engine), provider, lambda *args: None)
    result = service.execute(
        owners[0],
        "alice",
        AnswerRequest(
            question="Où a lieu le lancement ?", model=model, allow_external_processing=True
        ),
        lambda: True,
    )
    assert result.state == "answered" and result.model == model and calls == [1]
    assert result.claims[0].evidence[0].source_id == "S1"
    with engine.connect() as c:
        row = c.execute(text("SELECT reserved_tokens,outcome FROM generation_attempts")).one()
        assert row.reserved_tokens == 24576 and row.outcome == "answered"
        assert c.execute(text("SELECT count(*) FROM openai_trial_attempts")).scalar_one() == 1
        assert c.execute(text("SELECT lease_token FROM generation_limits")).scalar_one() is None


def test_token_capacity_rollback_preserves_daily_and_money_reservations(context, database):
    from app.repositories.generation import GenerationRepository

    engine, config = database
    owner = context[1][0]
    repo = GenerationRepository(engine)
    lease, _ = repo.acquire(owner, "alice", 24576)
    OpenAIBudgetRepository(engine).reserve("gpt-6-luna")
    repo.release(lease)
    command.downgrade(config, "0009_openai_trial")
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT sum(reserved_tokens) FROM generation_attempts")).scalar_one()
            == 24576
        )
    lease, _ = repo.acquire(owner, "alice", 3100)
    repo.release(lease)
    command.upgrade(config, "head")
    assert OpenAIBudgetRepository(engine).remaining_microusd() == 990000
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT sum(reserved_tokens) FROM generation_attempts")).scalar_one()
            == 27676
        )
