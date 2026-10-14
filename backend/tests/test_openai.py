import json
import time
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.openai import OpenAIProvider
from app.config import Settings
from app.models.answer import AnswerRequest
from app.models.conversation import MessageRequest
from app.models.document import DocumentError


@pytest.fixture(autouse=True)
def valid_price_window(monkeypatch):
    from datetime import date

    # Normal adapter tests must not depend on the wall-clock review deadline.
    monkeypatch.setattr("app.adapters.openai.PRICING_VALID_UNTIL", date.max)


class Budget:
    def __init__(self, exhausted=False):
        self.calls = []
        self.exhausted = exhausted

    def reserve(self, model):
        if self.exhausted:
            raise DocumentError(429, "openai_budget_exhausted")
        self.calls.append(model)
        return uuid4()


def settings(tmp_path):
    key = tmp_path / "key"
    key.write_text("synthetic-test-key")
    return Settings(openai_local_enabled=True, openai_api_key_file=key)


def test_default_and_allowlist():
    assert AnswerRequest(question="Une question ?").model == "groq"
    assert MessageRequest(request_id=uuid4(), question="Une question ?").model == "groq"
    with pytest.raises(ValidationError):
        AnswerRequest(question="Une question ?", model="arbitrary-paid-model")


@pytest.mark.parametrize("model,effort", [("gpt-6-luna", "none"), ("gpt-6.1-sol", "low")])
def test_explicit_model_private_structured_request_and_prior_reservation(tmp_path, model, effort):
    budget = Budget()

    def handler(request):
        assert budget.calls == [model]
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == model and payload["store"] is False
        assert payload["service_tier"] == "default"
        assert payload["reasoning_effort"] == effort
        assert payload["response_format"]["type"] == "json_schema"
        assert "tools" not in payload
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    provider = OpenAIProvider(settings(tmp_path), model, budget, httpx.MockTransport(handler))
    assert (
        provider.generate([{"role": "user", "content": "Bonjour"}], time.monotonic() + 30).content
        == "{}"
    )


def test_exhausted_budget_never_sends(tmp_path):
    def handler(request):
        pytest.fail("No HTTP request allowed after budget exhaustion")

    provider = OpenAIProvider(
        settings(tmp_path), "gpt-6-luna", Budget(True), httpx.MockTransport(handler)
    )
    with pytest.raises(DocumentError, match="openai_budget_exhausted"):
        provider.generate([], time.monotonic() + 30)


def test_timeout_keeps_reservation_and_does_not_retry(tmp_path):
    from app.adapters.groq import ProviderError

    budget = Budget()

    def handler(request):
        raise httpx.ReadTimeout("synthetic")

    provider = OpenAIProvider(
        settings(tmp_path), "gpt-6-luna", budget, httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError) as error:
        provider.generate([], time.monotonic() + 30)
    assert not error.value.transient and budget.calls == ["gpt-6-luna"]


def test_cloud_disabled_and_oversized_request_never_reserved(tmp_path):
    from app.adapters.groq import ProviderError

    config = settings(tmp_path)
    config.cloud_runtime = True
    budget = Budget()
    provider = OpenAIProvider(config, "gpt-6-luna", budget)
    assert not provider.ready()
    with pytest.raises(ProviderError, match="llm_not_configured"):
        provider.generate([], time.monotonic() + 30)
    config.cloud_runtime = False
    with pytest.raises(ProviderError, match="context_budget"):
        provider.generate([{"role": "user", "content": "x" * 16001}], time.monotonic() + 30)
    assert not budget.calls


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
def test_paid_models_preserve_abstention_consent_and_citation_validation(model):
    from test_answer_service import execute
    from test_answers import hit, output

    service, quotas, provider, body, active = execute([], [])
    body.model = model
    result = service.execute(uuid4(), "session", body, active)
    assert not result.provider_called and not provider.calls and not quotas.attempts
    for allow, reply, code in [
        (False, [], "external_processing_required"),
        (True, [output("S99")], "invalid_citations"),
    ]:
        service, quotas, provider, body, active = execute([hit()], reply, allow=allow)
        body.model = model
        with pytest.raises(DocumentError, match=code):
            service.execute(uuid4(), "session", body, active)
        assert provider.calls == int(allow)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "llm_unavailable"),
        (429, "openai_provider_quota"),
        (500, "llm_unavailable"),
        (302, "llm_unavailable"),
    ],
)
def test_http_errors_never_retry_or_leak_provider_details(tmp_path, status, code):
    from app.adapters.groq import ProviderError

    budget = Budget()
    provider = OpenAIProvider(
        settings(tmp_path),
        "gpt-6-luna",
        budget,
        httpx.MockTransport(
            lambda request: httpx.Response(
                status, text="PRIVATE DETAILS", headers={"location": "https://example.com"}
            )
        ),
    )
    with pytest.raises(ProviderError) as error:
        provider.generate([], time.monotonic() + 30)
    assert error.value.code == code and not error.value.transient
    assert "PRIVATE" not in str(error.value) and len(budget.calls) == 1


def test_price_expiry_stops_before_budget_or_network(tmp_path, monkeypatch):
    from datetime import date

    from app.adapters.groq import ProviderError

    monkeypatch.setattr("app.adapters.openai.PRICING_VALID_UNTIL", date(2000, 1, 1))
    budget = Budget()
    provider = OpenAIProvider(settings(tmp_path), "gpt-6-luna", budget)
    with pytest.raises(ProviderError, match="openai_pricing_review_required"):
        provider.generate([], time.monotonic() + 30)
    assert not budget.calls


@pytest.mark.parametrize("model", ["groq", "gpt-6-luna", "gpt-6.1-sol"])
def test_conversation_propagates_model_without_paid_replay(model):
    from test_conversation_service import setup

    owner, conversation, body, repo, answers, service = setup()
    body.model = model
    service.execute(owner, "session", conversation, body, lambda: True)
    assert answers.execute.call_args.args[2].model == model
    repo.begin.return_value = (repo.complete.return_value, False)
    service.execute(owner, "session", conversation, body, lambda: True)
    assert answers.execute.call_count == 1


def test_catalog_is_private_and_cloud_never_advertises_openai(tmp_path, monkeypatch):
    from datetime import date
    from unittest.mock import Mock

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.services.models import model_catalog

    monkeypatch.setattr("app.services.models.PRICING_VALID_UNTIL", date.max)
    from app.api.identity import get_repository

    app = create_app(Settings(database_url=None))
    app.dependency_overrides[get_repository] = lambda: Mock()
    with TestClient(app) as client:
        response = client.get("/api/v1/models")
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    config = settings(tmp_path)
    budget = Mock()
    budget.remaining_microusd.return_value = 40_000
    catalog = model_catalog(config, budget)
    choices = {item["id"]: item for item in catalog["models"]}
    assert choices["gpt-6-luna"]["available"]
    assert not choices["gpt-6.1-sol"]["available"]
    config.cloud_runtime = True
    budget.reset_mock()
    assert [item["id"] for item in model_catalog(config, budget)["models"]] == ["groq"]
    budget.remaining_microusd.assert_not_called()


def test_openai_quota_does_not_block_groq_or_retry():
    from test_answer_service import execute
    from test_answers import hit

    from app.adapters.groq import ProviderError

    service, quotas, provider, body, active = execute(
        [hit()], [ProviderError("openai_provider_quota")]
    )
    body.model = "gpt-6-luna"
    with pytest.raises(DocumentError) as error:
        service.execute(uuid4(), "session", body, active)
    assert error.value.status == 429
    assert provider.calls == 1 and quotas.blocked is None and quotas.released


def test_cloud_requires_production_opt_in_and_server_secret(tmp_path, monkeypatch):
    from datetime import date
    from unittest.mock import Mock

    from pydantic import SecretStr

    from app.services.models import model_catalog

    monkeypatch.setattr("app.services.models.PRICING_VALID_UNTIL", date.max)
    config = settings(tmp_path)
    config.cloud_runtime = True
    config.openai_cloud_enabled = True
    config.vercel_env = "preview"
    config.openai_api_key = SecretStr("synthetic-cloud-key")
    budget = Mock()
    budget.remaining_microusd.return_value = 990_000
    provider = OpenAIProvider(config, "gpt-6-luna", budget)
    assert not provider.ready()
    assert len(model_catalog(config, budget)["models"]) == 1
    config.vercel_env = "production"
    assert provider.ready()
    assert len(model_catalog(config, budget)["models"]) == 3
    config.openai_api_key = None
    assert not provider.ready()  # Never read the local key file in the cloud.
    config.cloud_runtime = False
    config.openai_local_enabled = False
    assert not provider.ready()  # Cloud credentials cannot enable local calls.
