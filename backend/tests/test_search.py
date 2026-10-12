from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.search import SearchHit, SearchRequest
from app.services.search import query_text, select_hits


def hit(text="Texte", start=0, end=100, score=0.9, document_id=None, ordinal=1):
    return SearchHit(
        document_id=document_id or uuid4(),
        generation=1,
        ordinal=ordinal,
        filename="notes.txt",
        text=text,
        token_count=100,
        kind="line",
        start_number=1,
        end_number=2,
        start_offset=start,
        end_offset=end,
        score=score,
    )


def test_question_selection_and_limits_are_explicit():
    for payload in [
        {"question": " "},
        {"question": "x", "document_ids": []},
        {"question": "x", "top_k": 11},
        {"question": "x", "owner_id": str(uuid4())},
        {"question": "x" * 1001},
    ]:
        with pytest.raises(ValidationError):
            SearchRequest(**payload)
    identifier = uuid4()
    assert SearchRequest(
        question="  Bonjour  ", document_ids=[identifier, identifier]
    ).document_ids == [identifier]


def test_follow_up_uses_user_questions_without_assistant_claims():
    request = SearchRequest(
        question="Et pour UDP ?",
        history=[
            {"role": "user", "content": "Que garantit TCP ?"},
            {"role": "assistant", "content": "Une affirmation inventée."},
        ],
    )
    result = query_text(request)
    assert "TCP" in result and "UDP" in result and "inventée" not in result
    assert query_text(SearchRequest(question="Bonjour")) == "Bonjour"


def test_threshold_duplicate_overlap_top_k_and_context_budget():
    identifier = uuid4()
    hits = [
        hit("Premier", document_id=identifier),
        hit(" Premier ", score=0.89),
        hit("Presque contenu", start=10, end=90, document_id=identifier, ordinal=2),
        hit("Passage voisin", start=80, end=180, document_id=identifier, ordinal=3),
        hit("Sous le seuil", score=0.5),
    ]
    selected = select_hits(hits, top_k=5, threshold=0.8, budget=200)
    assert [h.ordinal for h in selected] == [1, 3]
    assert select_hits(hits, top_k=1, threshold=0.8)[0].text == "Premier"
    assert select_hits(hits, top_k=5, threshold=0.99) == []
