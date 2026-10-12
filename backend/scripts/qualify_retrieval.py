"""Real E5 + exact PostgreSQL retrieval; tune development questions only."""

import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.adapters.storage import PrivateStorage
from app.config import Settings, build_engine
from app.models.document import UploadRequest
from app.models.search import SearchRequest
from app.repositories.documents import DocumentRepository
from app.repositories.identity import IdentityRepository
from app.repositories.indexes import IndexRepository
from app.repositories.jobs import JobRepository
from app.repositories.search import SearchRepository
from app.services.documents import DocumentService
from app.services.embeddings import INDEX_VERSION
from app.services.extraction import ExtractedUnit
from app.services.search import SEARCH_VERSION, query_text, select_hits
from app.worker.consumer import Consumer
from app.worker.indexer import Indexer
from scripts.retrieval_metrics import annotation_span, covered


def metrics(rows, spans, threshold):
    cases = []
    recalls = []
    found = total = negatives = rejected = 0
    for row in rows:
        case, hits = row["case"], select_hits(row["candidates"], 5, threshold)
        expected = case["relevant_passage_ids"]
        recovered = [p for p in expected if covered(spans[p], hits)]
        if expected:
            recalls.append(len(recovered) / len(expected))
            found += len(recovered)
            total += len(expected)
        else:
            negatives += 1
            rejected += not hits
        cases.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": expected,
                "recovered": recovered,
                "returned": len(hits),
                "max_score": max((h.score for h in row["candidates"]), default=None),
                "sources": [
                    {"filename": h.filename, "ordinal": h.ordinal, "score": round(h.score, 6)}
                    for h in hits
                ],
            }
        )
    return {
        "recall_at_5": sum(recalls) / len(recalls),
        "answerable_questions": len(recalls),
        "relevant_annotations_found": found,
        "relevant_annotations_total": total,
        "out_of_corpus_questions": negatives,
        "out_of_corpus_no_match": rejected,
        "cases": cases,
    }


def main() -> None:
    settings = Settings()
    url = make_url(settings.database_url or "")
    if url.database != "assistant_rag_evaluation" or url.host != "db":
        raise RuntimeError("Dedicated local evaluation database required")
    command.upgrade(Config("alembic.ini"), "head")
    engine = build_engine(settings)
    assert engine is not None
    subject = "evaluation-" + str(uuid4())
    storage = PrivateStorage(settings.private_storage_path)
    indexer = Indexer(IndexRepository(engine), settings.embedding_path)
    identifiers = {}
    units_by_name = {}
    corpus = []
    owner = None
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    'INSERT INTO auth_user(id,name,email,"emailVerified",userna'
                    "me) VALUES (:s,:s,:e,false,:s)"
                ),
                {"s": subject, "e": subject + "@accounts.invalid"},
            )
            c.execute(
                text(
                    'INSERT INTO auth_session(id,"userId",token,"expiresAt","up'
                    "datedAt\") VALUES (:s,:s,:s,now()+interval '1 hour',now())"
                ),
                {"s": subject},
            )
        owner = IdentityRepository(engine).current_user(subject).id
        documents = DocumentRepository(engine)
        service = DocumentService(documents, storage, settings)
        consumer = Consumer(JobRepository(engine), storage, indexer)
        for filename in [
            "atelier-rag.pdf",
            "parcours-2026.docx",
            "reseau.txt",
            "politique-2025.txt",
        ]:
            file = Path("/evaluation/corpus") / filename
            raw = file.read_bytes()
            mime = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "txt": "text/plain",
            }[file.suffix[1:]]
            doc, token = service.reserve(
                owner,
                subject,
                UploadRequest(filename=filename, size_bytes=len(raw), content_type=mime),
            )
            identifiers[file.stem] = doc.id
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            service.uploads.begin_upload(doc.id, token_hash)
            temporary = storage.temporary()
            temporary.write_bytes(raw)
            service.uploads.complete_upload(
                doc.id, token_hash, len(raw), lambda: storage.commit(temporary, doc.id)
            )
            temporary.unlink()
            service.finalize(owner, doc.id)
        started = time.perf_counter()
        while any(
            documents.get(owner, identifier).state != "ready" for identifier in identifiers.values()
        ):
            if time.perf_counter() - started > 180 or not consumer.run_once():
                raise RuntimeError("Real corpus indexing failed")
        index_seconds = time.perf_counter() - started
        for name, identifier in identifiers.items():
            units = [
                ExtractedUnit(u.kind, u.number, u.text)
                for u in documents.units(owner, identifier, 0, 50)
            ]
            units_by_name[name] = units
            corpus.append(
                {
                    "document": name,
                    "units": len(units),
                    "chunks": documents.get(owner, identifier).chunk_count,
                }
            )
        annotations = json.loads(Path("/evaluation/reference_passages.json").read_text())
        spans = {
            a["id"]: (
                identifiers[a["document_id"]],
                *annotation_span(units_by_name[a["document_id"]], a),
            )
            for a in annotations
        }
        cases = [
            q
            for q in map(json.loads, Path("/evaluation/questions.jsonl").read_text().splitlines())
            if q["split"] == "development"
        ]
        assert len(cases) == 20 and all(q["split"] == "development" for q in cases)
        repository = SearchRepository(engine)
        rows = []
        latencies = []
        for case in cases:
            selection = (
                [identifiers[n] for n in case["document_ids"]]
                if case["document_ids"] is not None
                else None
            )
            request = SearchRequest(
                question=case["question"], history=case["history"], document_ids=selection
            )
            begun = time.perf_counter()
            vector = indexer.encoder.encode([query_text(request)], "query")[0]
            candidates = repository.candidates(owner, selection, vector)
            latencies.append(time.perf_counter() - begun)
            rows.append({"case": case, "candidates": candidates})
        grid = [round(0.65 + n * 0.005, 3) for n in range(71)]
        trials = [(t, metrics(rows, spans, t)) for t in grid]
        valid = [(t, m) for t, m in trials if m["recall_at_5"] >= 0.8]
        if not valid:
            raise RuntimeError("Recall@5 objective is not met")
        threshold, result = max(
            valid, key=lambda v: (v[1]["out_of_corpus_no_match"], v[1]["recall_at_5"], v[0])
        )
        report = {
            "status": "passed",
            "split": "development",
            "final_cases_evaluated": 0,
            "threshold": threshold,
            "threshold_selection": "maximize negative rejection then Recall@5 then threshold, "
            "requiring Recall@5 >= 0.8",
            "threshold_grid": [
                {
                    "threshold": t,
                    "recall_at_5": m["recall_at_5"],
                    "out_of_corpus_no_match": m["out_of_corpus_no_match"],
                }
                for t, m in trials
            ],
            "metrics": result,
            "corpus": corpus,
            "annotations_mapped": len(spans),
            "index_version": INDEX_VERSION,
            "search_version": SEARCH_VERSION,
            "corpus_index_seconds": round(index_seconds, 3),
            "warm_query_seconds": {
                "count": len(latencies),
                "median": round(sorted(latencies)[len(latencies) // 2], 3),
                "p95": round(sorted(latencies)[18], 3),
            },
            "corpus_sha256": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path("/evaluation/corpus").iterdir()
                if p.stem in identifiers
            },
            "evaluation_database": "assistant_rag_evaluation",
            "llm_calls": 0,
            "cloud_deployment": False,
            "cost_eur": 0,
        }
    finally:
        indexer.close()
        for identifier in identifiers.values():
            storage.delete(identifier)
        with engine.begin() as c:
            if owner is not None:
                c.execute(text("DELETE FROM documents WHERE owner_id=:owner"), {"owner": owner})
                c.execute(text("DELETE FROM users WHERE id=:owner"), {"owner": owner})
            c.execute(text('DELETE FROM auth_session WHERE "userId"=:s'), {"s": subject})
            c.execute(text("DELETE FROM auth_user WHERE id=:s"), {"s": subject})
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
