"""Probe CPU local sur passages de référence, sans chaîne RAG de production."""
import json
import hashlib
import platform
import resource
import statistics
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
start = time.perf_counter()
model = SentenceTransformer(MODEL, revision=REVISION, device="cpu")
loaded = time.perf_counter() - start
passages = json.loads((ROOT / "evaluation/reference_passages.json").read_text(encoding="utf-8"))
questions = [json.loads(s) for s in (ROOT / "evaluation/questions.jsonl").read_text(encoding="utf-8").splitlines()]
# Sélection AVANT encodage et mesure ; les questions finales ne sont pas utilisées.
development = [q for q in questions if q["split"] == "development"]
started = time.perf_counter()
vectors = model.encode(["passage: " + p["text"] for p in passages], batch_size=4, normalize_embeddings=True)
encode_time = time.perf_counter() - started
assert vectors.shape == (22, 384)
assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
lengths = [len(model.tokenizer.encode("passage: " + p["text"])) for p in passages]
assert max(lengths) <= model.max_seq_length
times, cases, recalls = [], [], []
for q in development:
    # Baseline déterministe d'un suivi : ajouter la dernière question utilisateur.
    previous = next((m["content"] for m in reversed(q["history"]) if m["role"] == "user"), "")
    query = (previous + " " + q["question"]).strip()
    begin = time.perf_counter()
    encoded = model.encode(["query: " + query], normalize_embeddings=True)[0]
    candidates = [i for i, p in enumerate(passages) if q["document_ids"] is None or p["document_id"] in q["document_ids"]]
    scores = vectors[candidates] @ encoded
    order = np.argsort(-scores, kind="stable")[:5]
    hits = [passages[candidates[int(i)]]["id"] for i in order]
    times.append(time.perf_counter() - begin)
    expected = set(q["relevant_passage_ids"])
    recall = len(expected & set(hits)) / len(expected) if expected else None
    if recall is not None:
        recalls.append(recall)
    cases.append({"id": q["id"], "top5": hits, "recall_at_5": recall, "top_score": float(scores[order[0]])})
report = {
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "manifest_sha256": hashlib.sha256((ROOT / "evaluation/manifest.json").read_bytes()).hexdigest(),
    "annotations_sha256": hashlib.sha256((ROOT / "evaluation/questions.jsonl").read_bytes()).hexdigest(),
    "top_k": 5, "prefixes": {"query": "query: ", "passage": "passage: "}, "normalize_embeddings": True,
    "scope": "WSL CPU local, passages canoniques courts, filtres de sélection ; pas pgvector, découpage production, isolation des comptes ou LLM",
    "model": MODEL, "revision": REVISION, "dimension": 384, "max_seq_length": model.max_seq_length,
    "python": platform.python_version(), "threads": 1,
    "versions": {p: version(p) for p in ["torch", "sentence-transformers", "transformers", "numpy", "huggingface-hub"]},
    "load_seconds_including_cache_or_download": round(loaded, 3),
    "encode_22_passages_seconds": round(encode_time, 3),
    "peak_rss_mib_linux": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
    "max_passage_tokens": max(lengths), "development_questions": len(development),
    "answerable_questions": len(recalls), "mean_recall_at_5": statistics.mean(recalls),
    "query_latency_ms_median": round(statistics.median(times) * 1000, 2),
    "query_latency_ms_p95": round(float(np.percentile(times, 95)) * 1000, 2),
    "final_questions_evaluated": 0, "cases": cases,
}
out = ROOT / "evaluation/reports"
out.mkdir(exist_ok=True)
(out / "embeddings-step0.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=False, indent=2))
