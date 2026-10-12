import re

import pytest

from app.services.chunking import ChunkConfig, split_units
from app.services.extraction import ExtractedUnit


class WordTokenizer:
    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def test_exact_unicode_text_coverage_overlap_and_physical_locations():
    units = [
        ExtractedUnit("page", 2, "Été à Paris. " + "information " * 320),
        ExtractedUnit("page", 5, "Suite importante. " + "conclusion " * 100),
    ]
    source = "\n\n".join(u.text for u in units)
    chunks = split_units(units, WordTokenizer())
    assert len(chunks) >= 2
    covered = set()
    for i, chunk in enumerate(chunks, 1):
        assert chunk.ordinal == i and 0 < chunk.token_count <= 300
        assert chunk.text == source[chunk.start_offset : chunk.end_offset]
        assert chunk.start_number in {2, 5} and chunk.end_number in {2, 5}
        covered.update(range(chunk.start_offset, chunk.end_offset))
    assert covered == set(range(len(source)))
    assert chunks[1].start_offset < chunks[0].end_offset
    assert chunks[0].start_number == 2 and chunks[-1].end_number == 5
    assert chunks == split_units(units, WordTokenizer())


def test_paragraph_and_sentence_boundaries_are_preferred():
    first = " ".join(["mot"] * 210) + "."
    units = [
        ExtractedUnit("paragraph", 1, first),
        ExtractedUnit("paragraph", 3, " ".join(["suite"] * 200)),
    ]
    chunks = split_units(units, WordTokenizer())
    assert chunks[0].text == first + "\n\n"
    assert chunks[0].end_number == 1
    assert chunks[-1].end_number == 3


def test_invalid_configuration_and_passage_limit_stop_planning():
    with pytest.raises(ValueError):
        ChunkConfig(tokens=300, overlap=300)
    with pytest.raises(ValueError):
        ChunkConfig(tokens=510)
    with pytest.raises(ValueError, match="passage_quota"):
        split_units(
            [ExtractedUnit("line", 1, "mot " * 2000)], WordTokenizer(), ChunkConfig(max_chunks=2)
        )


def test_long_unbroken_text_and_empty_input_remain_bounded():
    class CharacterTokenizer:
        def offsets(self, text):
            return [(i, i + 1) for i in range(len(text))]

    source = "é" * 2000
    chunks = split_units([ExtractedUnit("line", 7, source)], CharacterTokenizer())
    assert chunks[-1].end_offset == len(source)
    assert all(c.token_count <= 300 and c.start_number == 7 for c in chunks)
    assert split_units([], WordTokenizer()) == []


def test_multiple_subtokens_for_one_unicode_character_always_make_progress():
    class SharedOffsetTokenizer:
        def offsets(self, text):
            return [(i, i + 1) for i in range(len(text)) for _ in range(2)]

    source = "é" * 6
    chunks = split_units(
        [ExtractedUnit("line", 1, source)],
        SharedOffsetTokenizer(),
        ChunkConfig(tokens=3, overlap=1),
    )
    assert "".join(chunk.text for chunk in chunks) == source
    assert all(chunk.token_count <= 3 for chunk in chunks)
