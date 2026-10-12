from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_answers import hit, output

from app.adapters.groq import Completion, ProviderError
from app.models.answer import AnswerRequest
from app.models.document import DocumentError
from app.services.answers import AnswerService


class Search:
    def __init__(self, hits):
        self.hits = hits

    def execute(self, *args):
        return SimpleNamespace(hits=self.hits)


class Quotas:
    def __init__(self):
        self.attempts = []
        self.finished = []
        self.released = False
        self.blocked = None

    def reserve(self, *args):
        identifier = uuid4()
        self.attempts.append(identifier)
        return identifier

    def acquire(self, *args):
        return uuid4(), self.reserve()

    def active(self, *args):
        return True

    def release(self, *args):
        self.released = True

    def block(self, seconds):
        self.blocked = seconds

    def finish_attempt(self, identifier, outcome, *args):
        self.finished.append(outcome)


class Provider:
    def __init__(self, replies):
        self.replies, self.calls = replies, 0

    def ready(self):
        return True

    def generate(self, *args):
        result = self.replies[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return Completion(result, 50, 30)


def execute(hits, replies, allow=True, active=lambda: True, verify=lambda *args: None):
    quotas, provider = Quotas(), Provider(replies)
    service = AnswerService(Search(hits), quotas, provider, verify, sleep=lambda n: None)
    return (
        service,
        quotas,
        provider,
        AnswerRequest(question="Où ?", allow_external_processing=allow),
        active,
    )


def test_no_context_skips_provider_and_consumes_no_quota():
    service, quotas, provider, body, active = execute([], [])
    result = service.execute(uuid4(), "session", body, active)
    assert result.state == "insufficient_context" and not result.provider_called
    assert not quotas.attempts and not provider.calls


def test_consent_missing_never_calls_external_provider():
    service, quotas, provider, body, active = execute([hit()], [], allow=False)
    with pytest.raises(DocumentError, match="external_processing_required"):
        service.execute(uuid4(), "session", body, active)
    assert not provider.calls and not quotas.attempts


def test_transient_retry_reserves_again_and_returns_server_resolved_sources():
    service, quotas, provider, body, active = execute(
        [hit()], [ProviderError("llm_unavailable", transient=True), output()]
    )
    result = service.execute(uuid4(), "session", body, active)
    assert result.state == "answered" and result.answer.endswith("[S1]")
    assert result.sources[0].filename == "notes.txt" and provider.calls == 2
    assert len(quotas.attempts) == 2 and quotas.finished == ["failed", "answered"]
    assert quotas.released


def test_429_stops_without_retry_and_invalid_citation_is_never_success():
    for reply, code in [
        (ProviderError("provider_quota", retry_after=42), "provider_quota"),
        (output("S99"), "invalid_citations"),
    ]:
        service, quotas, provider, body, active = execute([hit()], [reply])
        with pytest.raises(DocumentError, match=code):
            service.execute(uuid4(), "session", body, active)
        assert provider.calls == 1 and quotas.finished == ["failed"] and quotas.released
        if code == "provider_quota":
            assert quotas.blocked == 42


def test_session_revoked_or_source_deleted_during_generation_prevents_publication():
    for revoked in [True, False]:
        checks = []

        def verify(*args):
            checks.append(1)
            if len(checks) == 3 and not revoked:
                raise DocumentError(409, "source_unavailable")

        calls = []

        def active():
            calls.append(1)
            return len(calls) < 3 if revoked else True

        service, quotas, provider, body, _ = execute([hit()], [output()], verify=verify)
        with pytest.raises(
            DocumentError, match="session_expired" if revoked else "source_unavailable"
        ):
            service.execute(uuid4(), "session", body, active)
        assert quotas.released and quotas.finished == ["revoked" if revoked else "failed"]
