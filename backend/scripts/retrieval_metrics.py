import re
from uuid import UUID

from app.models.search import SearchHit
from app.services.extraction import ExtractedUnit


def annotation_span(units: list[ExtractedUnit], annotation: dict) -> tuple[int, int]:
    kind, number = next(iter(annotation["locator"].items()))
    pattern = r"\s+".join(re.escape(word) for word in annotation["text"].split())
    offset = 0
    for unit in units:
        if unit.kind == kind and unit.number == number:
            match = re.search(pattern, unit.text)
            if match:
                return offset + match.start(), offset + match.end()
        offset += len(unit.text) + 2
    raise ValueError("Annotation is not found at its physical locator")


def covered(span: tuple[UUID, int, int], hits: list[SearchHit]) -> bool:
    document, start, end = span
    intervals = sorted((h.start_offset, h.end_offset) for h in hits if h.document_id == document)
    cursor = start
    for left, right in intervals:
        if left > cursor:
            break
        if right > cursor:
            cursor = right
        if cursor >= end:
            return True
    return False
