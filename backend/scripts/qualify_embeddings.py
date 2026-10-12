"""Real offline E5 qualification on public synthetic fixtures; no database or LLM."""

import json
import resource
import time
from pathlib import Path

from app.adapters.embeddings import E5Encoder, E5Tokenizer
from app.adapters.model_snapshot import validate_snapshot
from app.config import Settings
from app.services.chunking import split_units
from app.services.embeddings import INDEX_VERSION, PASSAGE_PREFIX, QUERY_PREFIX, validate_vectors
from app.services.extraction import ExtractedUnit, extract


def main() -> None:
    path = Settings().embedding_path
    validate_snapshot(path)
    tokenizer = E5Tokenizer(path)
    corpus = []
    texts = []
    for filename in ["atelier-rag.pdf", "parcours-2026.docx", "reseau.txt", "politique-2025.txt"]:
        file = Path("/evaluation/corpus") / filename
        units = extract(file, file.suffix[1:])
        chunks = split_units(units, tokenizer)
        source = "\n\n".join(unit.text for unit in units)
        assert chunks and chunks[0].start_offset == 0 and chunks[-1].end_offset == len(source)
        for chunk in chunks:
            assert chunk.text == source[chunk.start_offset : chunk.end_offset]
            assert chunk.start_number == units[chunk.start_unit - 1].number
            assert chunk.end_number == units[chunk.end_unit - 1].number
            assert 0 < chunk.token_count <= 300
            texts.append(chunk.text)
        corpus.append({"filename": filename, "units": len(units), "passages": len(chunks)})
    # Representative full token-budget batch, separate from the held-out questions.
    representative = split_units(
        [ExtractedUnit("line", 1, "Le projet conserve les documents privés. " * 1500)], tokenizer
    )
    batch = [chunk.text for chunk in representative if chunk.token_count >= 290][:16]
    assert len(batch) == 16
    started = time.perf_counter()
    encoder = E5Encoder(path)
    validate_vectors(encoder.encode(batch), 16)
    process_seconds = time.perf_counter() - started
    validate_vectors(encoder.encode(["Comment conserver mes documents ?"], "query"), 1)
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    started = time.perf_counter()
    model = SentenceTransformer(str(path), device="cpu", local_files_only=True)
    load_seconds = time.perf_counter() - started
    timings = []
    for _ in range(2):
        started = time.perf_counter()
        encoded = model.encode(
            [PASSAGE_PREFIX + item for item in batch],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        validate_vectors(encoded.tolist(), 16)
        timings.append(time.perf_counter() - started)
    for i in range(0, len(texts), 16):
        encoded = model.encode(
            [PASSAGE_PREFIX + item for item in texts[i : i + 16]],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        validate_vectors(encoded.tolist(), len(texts[i : i + 16]))
    ids = model.tokenizer([PASSAGE_PREFIX + item for item in batch], truncation=False)["input_ids"]
    assert max(map(len, ids)) <= 512
    query = model.encode(
        [QUERY_PREFIX + "Comment conserver mes documents ?"], normalize_embeddings=True
    )
    validate_vectors(query.tolist(), 1)
    print(
        json.dumps(
            {
                "status": "passed",
                "index_version": INDEX_VERSION,
                "corpus": corpus,
                "representative_batch": 16,
                "max_prefixed_tokens": max(map(len, ids)),
                "bounded_process_seconds": round(process_seconds, 3),
                "model_load_seconds": round(load_seconds, 3),
                "first_batch_seconds": round(timings[0], 3),
                "warm_batch_seconds": round(timings[1], 3),
                "encoder_peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1
                ),
                "qualification_peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
                ),
                "model_files_bytes": sum(
                    file.stat().st_size for file in path.rglob("*") if file.is_file()
                ),
                "dimension": 384,
                "normalization": "l2",
                "device": "cpu",
                "cpu_threads": 1,
                "runtime_network": False,
                "llm_calls": 0,
                "cloud_deployment": False,
                "cost_eur": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
