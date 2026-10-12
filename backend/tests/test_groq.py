import json
import time

import httpx
import pytest

from app.adapters.groq import GroqProvider, ProviderError, retry_delay
from app.config import Settings


def provider(handler):
    return GroqProvider(
        Settings(groq_api_key="synthetic-test-key", llm_free_plan_confirmed=True),
        httpx.MockTransport(handler),
    )


def valid_reply():
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 20},
    }


def test_groq_request_is_bounded_strict_without_paid_tools_or_redirects():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "openai/gpt-oss-120b"
        assert payload["max_completion_tokens"] == 600 and payload["reasoning_effort"] == "low"
        assert payload["response_format"]["json_schema"]["strict"]
        assert "tools" not in payload and "service_tier" not in payload
        return httpx.Response(200, json=valid_reply())

    assert provider(handler).generate([], time.monotonic() + 30).completion_tokens == 20
    assert "synthetic-test-key" not in repr(Settings(groq_api_key="synthetic-test-key"))
    assert not GroqProvider(Settings(llm_free_plan_confirmed=False)).ready()


def test_provider_quota_retry_after_and_network_failure_have_no_raw_payload():
    for status, expected, transient in [
        (429, "provider_quota", False),
        (503, "llm_unavailable", True),
        (401, "llm_unavailable", False),
        (307, "llm_unavailable", False),
    ]:
        with pytest.raises(ProviderError) as error:
            provider(
                lambda r: httpx.Response(
                    status,
                    headers={"retry-after": "45"},
                    json={"error": "synthetic confidential text"},
                )
            ).generate([], time.monotonic() + 30)
        assert error.value.code == expected and error.value.transient == transient
        assert "confidential" not in str(error.value)
        assert error.value.retry_after == 45
    assert retry_delay("invalid") == 60
    assert retry_delay("nan") == 60

    def timeout(request):
        raise httpx.ReadTimeout("synthetic confidential text")

    with pytest.raises(ProviderError, match="generation_timeout"):
        provider(timeout).generate([], time.monotonic() + 30)


def test_truncated_oversized_invalid_usage_and_malformed_responses_fail():
    invalid = valid_reply()
    invalid["choices"][0]["finish_reason"] = "length"
    oversized = valid_reply()
    oversized["choices"][0]["message"]["content"] = "x" * 40000
    budget = valid_reply()
    budget["usage"]["completion_tokens"] = 601
    for body in [invalid, oversized, budget, {}]:
        with pytest.raises(ProviderError, match="invalid_llm_output"):
            provider(lambda r: httpx.Response(200, json=body)).generate([], time.monotonic() + 30)


def test_simulated_endpoint_cannot_be_used_with_main_database():
    p = GroqProvider(
        Settings(
            groq_api_key="synthetic-test-key",
            llm_free_plan_confirmed=True,
            database_url="postgresql://localhost/assistant_rag",
            llm_test_endpoint="http://llm-test:8000/openai/v1/chat/completions",
        )
    )
    with pytest.raises(ProviderError, match="llm_not_configured"):
        p.generate([], time.monotonic() + 30)
