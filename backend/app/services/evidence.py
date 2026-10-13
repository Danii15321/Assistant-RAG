"""Stable, exact source excerpts selected by ID rather than rewritten by a model."""

import re


def source_excerpts(text: str) -> dict[str, str]:
    excerpts: list[str] = []
    # Keep neighbouring sentences together: pronouns and replacement rules often
    # refer to facts in the preceding sentence. Paragraph boundaries stay exact.
    for sentence in re.split(r"\n\s*\n", text):
        sentence = sentence.strip()
        while sentence:
            end = min(400, len(sentence))
            if end < len(sentence):
                boundary = sentence.rfind(" ", 0, end)
                if boundary > 0:
                    end = boundary
            excerpts.append(sentence[:end].rstrip())
            sentence = sentence[end:].lstrip()
    return {f"E{i}": excerpt for i, excerpt in enumerate(excerpts, 1)}
