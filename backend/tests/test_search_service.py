import json
from unittest.mock import Mock
from uuid import uuid4

import pytest
from test_search import hit

from app.models.document import DocumentError
from app.models.search import SearchRequest
from app.services.search import SearchService


def service():
    repository, jobs = Mock(), Mock()
    repository.validate_selection.return_value = True
    jobs.result.return_value = {"status": "done", "embedding": json.dumps([1.0] + [0.0] * 383)}
    repository.candidates.return_value = [hit()]
    return SearchService(repository, jobs, 0.8, timeout=0), repository, jobs


def test_empty_corpus_does_not_encode_or_submit():
    search, repository, jobs = service()
    repository.validate_selection.return_value = False
    response = search.execute(uuid4(), "session", SearchRequest(question="Question"), lambda: True)
    assert response.status == "empty_corpus" and response.hits == []
    jobs.submit.assert_not_called()


def test_timeout_failure_and_revoked_session_remove_private_query():
    for status, active, code in [
        ("pending", True, "search_timeout"),
        ("failed", True, "query_too_long"),
        ("pending", False, "session_expired"),
    ]:
        search, _, jobs = service()
        jobs.result.return_value = {"status": status, "error_code": "query_too_long"}
        with pytest.raises(DocumentError, match=code):
            search.execute(uuid4(), "session", SearchRequest(question="Question"), lambda: active)
        jobs.remove.assert_called_once()


def test_selection_is_rechecked_after_encoding_and_never_widened():
    search, repository, jobs = service()
    repository.validate_selection.side_effect = [True, DocumentError(404, "selection_unavailable")]
    with pytest.raises(DocumentError, match="selection_unavailable"):
        search.execute(
            uuid4(),
            "session",
            SearchRequest(question="Question", document_ids=[uuid4()]),
            lambda: True,
        )
    repository.candidates.assert_not_called()
    jobs.remove.assert_called_once()
