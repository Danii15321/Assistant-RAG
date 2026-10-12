from test_search import hit

from app.services.extraction import ExtractedUnit
from scripts.retrieval_metrics import annotation_span, covered


def test_annotation_mapping_requires_physical_locator_and_exact_words():
    units = [ExtractedUnit("page", 2, "Avant. Une phrase\nsur deux lignes. Après.")]
    start, end = annotation_span(
        units, {"text": "Une phrase sur deux lignes.", "locator": {"page": 2}}
    )
    assert units[0].text[start:end] == "Une phrase\nsur deux lignes."


def test_recall_counts_complete_union_coverage_without_overlap_double_count():
    first = hit(start=0, end=60)
    second = hit(start=50, end=100, document_id=first.document_id, ordinal=2)
    assert covered((first.document_id, 20, 90), [first, second])
    assert not covered((first.document_id, 20, 90), [first])
    assert not covered((first.document_id, 20, 90), [hit(start=0, end=100)])
