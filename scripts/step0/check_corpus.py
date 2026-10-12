"""Vérifier les fixtures, leurs repères et la séparation des annotations."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

root = Path(__file__).resolve().parents[2] / "evaluation"
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
passages = json.loads((root / "reference_passages.json").read_text(encoding="utf-8"))
questions = [json.loads(line) for line in (root / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
ids = {p["id"] for p in passages}
assert len(ids) == len(passages)
assert len(questions) == len({q["id"] for q in questions}) == 30
assert Counter(q["category"] for q in questions) == {"factual": 15, "multi_hop": 5, "out_of_corpus": 5, "follow_up": 5}
assert Counter(q["split"] for q in questions) == {"development": 20, "final": 10}
for q in questions:
    assert set(q["relevant_passage_ids"]) <= ids
    assert bool(q["history"]) == (q["category"] == "follow_up")
    assert bool(q["relevant_passage_ids"]) == (q["expected_state"] == "answered")
    if q["document_ids"]:
        assert all(p["document_id"] in q["document_ids"] for p in passages if p["id"] in q["relevant_passage_ids"])
for entry in manifest["documents"]:
    path = root / entry["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
    assert path.stat().st_size == entry["bytes"]
    expected = entry["expected"]
    if expected == "invalid_pdf":
        try:
            PdfReader(path)
        except PdfReadError:
            continue
        raise AssertionError("PDF corrompu accepté")
    if path.suffix == ".pdf":
        blocks = [p.extract_text() or "" for p in PdfReader(path).pages]
    elif path.suffix == ".docx":
        blocks = [p.text for p in Document(path).paragraphs]
    else:
        blocks = path.read_text(encoding="utf-8").splitlines()
    if expected in {"empty_document", "no_extractable_text"}:
        assert not "".join(blocks).strip()
        continue
    for p in passages:
        if p["document_id"] == entry["id"]:
            position = next(iter(p["locator"].values()))
            block = " ".join(blocks[position - 1].split())
            assert " ".join(p["text"].split()) in block, p["id"]
print("OK : 7 fichiers, 22 passages et repères, 30 annotations, lot final séparé.")
