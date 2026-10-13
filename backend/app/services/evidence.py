"""Stable, exact source excerpts selected by ID rather than rewritten by a model."""

import re


def source_excerpts(text: str) -> dict[str, str]:
    excerpts: list[str] = []
    # Keep neighbouring sentences together: pronouns and replacement rules often
    # refer to facts in the preceding sentence. Paragraph boundaries stay exact.
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        boundaries = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", paragraph)]
        boundaries.append(len(paragraph))
        start = 0
        while start < len(paragraph):
            limit = min(start + 400, len(paragraph))
            ends = [end for end in boundaries if start < end <= limit]
            end = max(ends) if ends else limit
            if not ends and end < len(paragraph):
                space = paragraph.rfind(" ", start, end)
                if space > start:
                    end = space
            excerpts.append(paragraph[start:end].strip())
            if end == len(paragraph):
                break
            previous = [boundary for boundary in boundaries if start < boundary < end]
            following = next(
                (boundary for boundary in boundaries if boundary > end), len(paragraph)
            )
            # Repeat a complete neighbouring sentence only when the next window
            # can also include new text; this guarantees progress and the bound.
            overlap = previous[-1] if previous else end
            start = overlap if following - overlap <= 400 else end
            while start < len(paragraph) and paragraph[start].isspace():
                start += 1
    return {f"E{i}": excerpt for i, excerpt in enumerate(excerpts, 1)}
