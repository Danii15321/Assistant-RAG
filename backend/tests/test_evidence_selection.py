import json

import pytest
from test_answers import hit

from app.models.document import DocumentError
from app.models.search import SearchRequest
from app.services.generation import build_context, validate_answer


def selected(source="S1", excerpt="E1", text="Le lancement a lieu à Lyon."):
    return json.dumps(
        {
            "state": "answered",
            "claims": [{"text": text, "evidence": [{"source_id": source, "excerpt_id": excerpt}]}],
        }
    )


def test_model_selects_server_excerpt_and_cannot_rewrite_the_quote():
    source = hit("Le lancement a lieu à Lyon\nle 12 décembre.\n\nLa salle est A42.")
    context = build_context(SearchRequest(question="Où ?"), [source])
    payload = json.loads(context.messages[-1]["content"].split("SOURCES\n", 1)[1])
    assert payload[0]["excerpts"][0] == {
        "id": "E1",
        "text": "Le lancement a lieu à Lyon\nle 12 décembre.",
    }
    answer = validate_answer(selected(), context.sources)
    assert answer.claims[0].evidence[0].quote == payload[0]["excerpts"][0]["text"]
    for raw in [selected(excerpt="E99"), selected(source="S99"), selected(text="Salle A42.")]:
        with pytest.raises(DocumentError, match="invalid_citations"):
            validate_answer(raw, context.sources)


def test_long_passages_are_partitioned_into_exact_bounded_excerpts():
    source = hit("Mot difficile " * 100)
    context = build_context(SearchRequest(question="Quoi ?"), [source])
    payload = json.loads(context.messages[-1]["content"].split("SOURCES\n", 1)[1])
    excerpts = payload[0]["excerpts"]
    assert len(excerpts) > 1
    assert all(0 < len(e["text"]) <= 400 and e["text"] in source.text for e in excerpts)
    assert " ".join(e["text"] for e in excerpts).split() == source.text.split()


def test_excerpt_preserves_the_antecedent_of_a_replacement_rule():
    paragraph = (
        "La politique du 1er septembre 2026 conserve les documents pendant 45 jours. "
        "Cette règle remplace la politique de 2025."
    )
    context = build_context(SearchRequest(question="Quelle règle prévaut ?"), [hit(paragraph)])
    answer = validate_answer(
        selected(text="La règle de 45 jours remplace la politique de 2025."), context.sources
    )
    assert answer.claims[0].evidence[0].quote == paragraph
    with pytest.raises(DocumentError, match="invalid_citations"):
        validate_answer(
            selected(text="La règle de 99 jours remplace celle de 2025."), context.sources
        )


def test_long_paragraph_windows_overlap_on_a_complete_sentence():
    paragraph = (
        "Présentation : " + "contexte " * 20 + ". "
        "Chaque passage contient 220 tokens et le chevauchement est de 40 tokens. "
        "Le modèle produit des vecteurs normalisés : " + "dimension " * 20 + "."
    )
    context = build_context(SearchRequest(question="Quel chevauchement ?"), [hit(paragraph)])
    answer = validate_answer(
        selected(excerpt="E2", text="Le chevauchement est de 40 tokens."), context.sources
    )
    quote = answer.claims[0].evidence[0].quote
    assert "Chaque passage contient 220 tokens et le chevauchement est de 40 tokens." in quote
    assert quote in paragraph and len(quote) <= 400
