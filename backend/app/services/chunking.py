import re
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services.extraction import ExtractedUnit


class OffsetTokenizer(Protocol):
    def offsets(self, text: str) -> list[tuple[int, int]]: ...


@dataclass(frozen=True)
class ChunkConfig:
    tokens: int = 300
    overlap: int = 50
    max_chunks: int = 20000

    def __post_init__(self) -> None:
        if not 1 <= self.tokens <= 500 or not 0 <= self.overlap < self.tokens:
            raise ValueError("chunk_configuration")
        if self.max_chunks < 1:
            raise ValueError("chunk_configuration")


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    token_count: int
    start_offset: int
    end_offset: int
    kind: str
    start_number: int
    end_number: int
    start_unit: int
    end_unit: int


def split_units(
    units: Sequence[ExtractedUnit], tokenizer: OffsetTokenizer, config: ChunkConfig = ChunkConfig()
) -> list[Chunk]:
    if not units:
        return []
    source = "\n\n".join(unit.text for unit in units)
    starts: list[int] = []
    cursor = 0
    for unit in units:
        starts.append(cursor)
        cursor += len(unit.text)
        cursor += 2
    boundaries = [m.end() for m in re.finditer(r"\n\n|[.!?](?:[ \t]+|\n+)", source)]
    chunks: list[Chunk] = []
    start = 0
    while start < len(source):
        # Bound each tokenizer allocation even for whitespace-heavy extracted units.
        window = source[start : start + 32768]
        offsets = tokenizer.offsets(window)
        if not offsets:
            if chunks:
                raise ValueError("chunk_empty_window")
            return []
        end = start + (
            offsets[config.tokens - 1][1] if len(offsets) > config.tokens else len(window)
        )
        if end < len(source):
            lower = start + offsets[min(len(offsets), config.tokens) // 2][0]
            candidate = bisect_right(boundaries, end) - 1
            if candidate >= 0 and boundaries[candidate] >= lower:
                end = boundaries[candidate]
        content_offsets = tokenizer.offsets(source[start:end])
        while len(content_offsets) > config.tokens:
            end = min(end - 1, start + content_offsets[config.tokens - 1][1])
            if end <= start:
                raise ValueError("chunk_token_limit")
            content_offsets = tokenizer.offsets(source[start:end])
        first = min(bisect_right(starts, start) - 1, len(units) - 1)
        # Separators belong to neither physical unit: locate the last source character.
        last = min(bisect_right(starts, end - 1) - 1, len(units) - 1)
        chunks.append(
            Chunk(
                len(chunks) + 1,
                source[start:end],
                len(content_offsets),
                start,
                end,
                units[first].kind,
                units[first].number,
                units[last].number,
                first + 1,
                last + 1,
            )
        )
        if len(chunks) > config.max_chunks:
            raise ValueError("passage_quota")
        if end == len(source):
            break
        overlap_index = max(0, len(content_offsets) - config.overlap)
        next_start = start + content_offsets[overlap_index][0] if config.overlap else end
        start = next_start if next_start > start else end
    return chunks
