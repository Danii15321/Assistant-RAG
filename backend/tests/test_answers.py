import json
from uuid import uuid4

import pytest

from app.models.document import DocumentError
from app.models.search import SearchHit, SearchRequest
from app.services.generation import build_context, validate_answer


def hit(text="Le lancement a lieu à Lyon le 12 décembre."):
    return SearchHit(
        document_id=uuid4(),
        generation=1,
        ordinal=1,
        filename="notes.txt",
        text=text,
        token_count=20,
        kind="line",
        start_number=1,
        end_number=1,
        start_offset=0,
        end_offset=len(text),
        score=0.95,
    )


def output(reference="S1", quote="Lyon", text="Le lancement a lieu à Lyon."):
    return json.dumps(
        {
            "state": "answered",
            "claims": [{"text": text, "evidence": [{"source_id": reference, "quote": quote}]}],
        },
        ensure_ascii=False,
    )


def test_sources_are_assigned_by_server_and_exact_quotes_are_required():
    context = build_context(SearchRequest(question="Où ?"), [hit()])
    answer = validate_answer(output(), context.sources)
    assert answer.state == "answered" and answer.claims[0].evidence[0].source_id == "S1"
    for raw in [
        output("S99"),
        output(quote="Paris"),
        output(text="Voir [S99]."),
        output(text="Le lancement est le 999 décembre."),
        output(text="Voir fictif.pdf."),
    ]:
        with pytest.raises(DocumentError, match="invalid_citations"):
            validate_answer(raw, context.sources)


def test_unstructured_empty_uncited_and_false_abstentions_are_rejected():
    sources = build_context(SearchRequest(question="Où ?"), [hit()]).sources
    for raw in [
        "bad JSON",
        json.dumps({"state": "answered", "claims": []}),
        json.dumps({"state": "answered", "claims": [{"text": "Lyon", "evidence": []}]}),
        json.dumps({"state": "insufficient_context", "claims": [{"text": "Lyon", "evidence": []}]}),
        json.dumps({"state": "answered", "claims": [], "filename": "invented"}),
    ]:
        with pytest.raises(DocumentError):
            validate_answer(raw, sources)
    answer = validate_answer(json.dumps({"state": "insufficient_context", "claims": []}), sources)
    assert answer.claims == []


def test_prompt_is_bounded_and_assistant_history_is_never_documentary_evidence():
    body = SearchRequest(
        question="Et où ?",
        history=[
            {"role": "assistant", "content": "Secret invented"},
            {"role": "user", "content": "Quand a lieu le lancement ?"},
        ],
    )
    context = build_context(body, [hit("Contexte {malveillant} " * 30), hit("Texte court.")])
    assert context.token_upper_bound <= 2500
    serialized = json.dumps(context.messages, ensure_ascii=False)
    assert "Secret invented" not in serialized and "Quand a lieu" in serialized
    assert "Contexte {malveillant}" in serialized
    with pytest.raises(DocumentError, match="context_budget"):
        build_context(SearchRequest(question="🧪" * 1000), [hit()])


def test_pdf_layout_whitespace_is_restored_to_the_exact_source_quote():
    source = hit("Le lancement est à Lyon\nle 12 décembre.")
    context = build_context(SearchRequest(question="Où ?"), [source])
    answer = validate_answer(
        output(quote="Lyon le 12 décembre", text="Lancement à Lyon le 12 décembre."),
        context.sources,
    )
    assert answer.claims[0].evidence[0].quote == "Lyon\nle 12 décembre"
    assert answer.claims[0].evidence[0].quote in source.text
    for quote in ["Lyon le 13 décembre", "lyon le 12 décembre", "Lyon, le 12 décembre"]:
        with pytest.raises(DocumentError, match="invalid_citations"):
            validate_answer(output(quote=quote), context.sources)
