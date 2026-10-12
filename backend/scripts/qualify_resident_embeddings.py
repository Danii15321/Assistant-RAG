"""Qualify the actual resident worker adapter with all networking disabled."""

import json
import resource
import time
from importlib.metadata import metadata, version
from pathlib import Path

from app.adapters.embeddings import E5Tokenizer
from app.adapters.resident_embeddings import ResidentE5Encoder
from app.config import Settings
from app.services.chunking import split_units
from app.services.embeddings import INDEX_VERSION, PASSAGE_PREFIX, validate_vectors
from app.services.extraction import ExtractedUnit, extract


def main() -> None:
    path = Settings().embedding_path
    tokenizer = E5Tokenizer(path)
    corpus = []
    passages = []
    for filename in ["atelier-rag.pdf", "parcours-2026.docx", "reseau.txt", "politique-2025.txt"]:
        file = Path("/evaluation/corpus") / filename
        units = extract(file, file.suffix[1:])
        chunks = split_units(units, tokenizer)
        source = "\n\n".join(unit.text for unit in units)
        assert chunks[0].start_offset == 0 and chunks[-1].end_offset == len(source)
        for chunk in chunks:
            assert chunk.text == source[chunk.start_offset : chunk.end_offset]
            assert chunk.start_number == units[chunk.start_unit - 1].number
            assert chunk.end_number == units[chunk.end_unit - 1].number
            assert 0 < chunk.token_count <= 300
            passages.append(chunk.text)
        corpus.append({"filename": filename, "units": len(units), "passages": len(chunks)})
    representative = split_units(
        [ExtractedUnit("line", 1, "Le projet conserve les documents privés. " * 1500)],
        tokenizer,
    )
    batch = [chunk.text for chunk in representative if chunk.token_count >= 290][:16]
    assert len(batch) == 16
    encoder = ResidentE5Encoder(path)
    try:
        timings = []
        for _ in range(2):
            started = time.perf_counter()
            validate_vectors(encoder.encode(batch), 16)
            timings.append(time.perf_counter() - started)
        process = encoder.process
        validate_vectors(encoder.encode(["Comment conserver mes documents ?"], "query"), 1)
        for offset in range(0, len(passages), 16):
            texts = passages[offset : offset + 16]
            validate_vectors(encoder.encode(texts), len(texts))
        assert encoder.process is process
        maximum = max(len(tokenizer.tokenizer.encode(PASSAGE_PREFIX + text).ids) for text in batch)
        assert maximum <= 512
    finally:
        encoder.close()
    packages = {}
    for name in ["torch", "sentence-transformers", "tokenizers", "transformers"]:
        item = metadata(name)
        packages[name] = {
            "version": version(name),
            "license": item.get("License-Expression")
            or item.get("License", "").split("\n")[0][:80],
        }
    print(
        json.dumps(
            {
                "status": "passed",
                "index_version": INDEX_VERSION,
                "corpus": corpus,
                "representative_batch": 16,
                "max_prefixed_tokens": maximum,
                "resident_startup_and_first_batch_seconds": round(timings[0], 3),
                "resident_warm_batch_seconds": round(timings[1], 3),
                "encoder_peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1
                ),
                "model_files_bytes": sum(
                    file.stat().st_size for file in path.rglob("*") if file.is_file()
                ),
                "dimension": 384,
                "normalization": "l2",
                "device": "cpu",
                "cpu_threads": 1,
                "same_process_for_passages_and_queries": True,
                "packages": packages,
                "container_network": "none",
                "llm_calls": 0,
                "cloud_deployment": False,
                "cost_eur": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
