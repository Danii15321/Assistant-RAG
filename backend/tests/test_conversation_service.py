from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models.answer import AnswerResponse
from app.models.conversation import Exchange, MessageRequest
from app.models.document import DocumentError
from app.models.search import HistoryMessage
from app.services.conversations import ConversationService


def setup():
    owner, conversation = uuid4(), uuid4()
    body = MessageRequest(
        request_id=uuid4(), question="Et le chevauchement ?", allow_external_processing=True
    )
    entry = Exchange(
        id=uuid4(),
        request_id=body.request_id,
        ordinal=2,
        question=body.question,
        document_ids=None,
        state="pending",
        answer=None,
        error_code=None,
        created_at=datetime.now(timezone.utc),
        completed_at=None,
    )
    repo, answers = Mock(), Mock()
    repo.begin.return_value = (entry, True)
    repo.active.return_value = True
    repo.history.return_value = [
        HistoryMessage(role="user", content="Les passages du guide Iris ?"),
        HistoryMessage(
            role="assistant", content="Une ancienne réponse ne constitue pas une source."
        ),
    ]
    result = AnswerResponse(
        state="insufficient_context",
        answer="Absent",
        claims=[],
        sources=[],
        provider_called=False,
        prompt_version="test",
        elapsed_ms=1,
    )
    answers.execute.return_value = result
    repo.complete.return_value = entry.model_copy(update={"state": "insufficient_context"})
    return owner, conversation, body, repo, answers, ConversationService(repo, answers)


def test_server_history_only_and_network_duplicate_never_calls_provider():
    owner, conversation, body, repo, answers, service = setup()
    service.execute(owner, "session", conversation, body, lambda: True)
    sent = answers.execute.call_args.args[2]
    assert sent.question == body.question
    assert [h.role for h in sent.history] == ["user"]
    assert "ancienne réponse" not in str(sent)
    repo.begin.return_value = (repo.complete.return_value, False)
    service.execute(owner, "session", conversation, body, lambda: True)
    assert answers.execute.call_count == 1


def test_provider_error_retains_question_and_expired_conversation_stops_generation():
    owner, conversation, body, repo, answers, service = setup()
    answers.execute.side_effect = DocumentError(502, "invalid_citations")
    with pytest.raises(DocumentError, match="invalid_citations"):
        service.execute(owner, "session", conversation, body, lambda: True)
    repo.fail.assert_called_once_with(
        owner, conversation, repo.begin.return_value[0].id, "invalid_citations"
    )
    answers.execute.side_effect = lambda o, s, b, active: active()
    repo.active.return_value = False
    with pytest.raises(DocumentError, match="generation_interrupted"):
        service.execute(owner, "session", conversation, body, lambda: True)
