"""Prototype de qualification, avec fixture fixe et endpoint coûteux protégé."""
import os
import re
import resource
import secrets
import threading
import time
from functools import lru_cache

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
MODEL_ID = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
_lock = threading.Lock()


@lru_cache(maxsize=1)
def encoder():
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    return SentenceTransformer(os.environ.get("EMBEDDING_PATH", MODEL_ID), device="cpu", revision=REVISION)


def run_probe() -> dict:
    import httpx
    import numpy as np

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise HTTPException(503, "missing_llm_configuration")
    start = time.perf_counter()
    with _lock:
        model = encoder()
        load_seconds = time.perf_counter() - start
        # Les textes sont fixes : ce prototype ne reçoit aucun document utilisateur.
        passages = [
            "La permanence Iris est le mardi de 14 à 16 heures dans la salle B214.",
            "Le serveur HTTPS du laboratoire Iris écoute le port 8443.",
        ]
        encode_start = time.perf_counter()
        vectors = model.encode(["passage: " + p for p in passages], normalize_embeddings=True)
        query = model.encode(["query: Où et quand a lieu la permanence Iris ?"], normalize_embeddings=True)[0]
        scores = vectors @ query
        top = int(np.argmax(scores))
        embeddings_seconds = time.perf_counter() - encode_start
        shape_valid = vectors.shape == (2, 384) and np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
        if not shape_valid or top != 0:
            raise HTTPException(502, "embedding_check_failed")
        payload = {
            "model": "openai/gpt-oss-120b", "temperature": 0,
            "max_completion_tokens": 600, "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": "Réponds en français uniquement depuis l'extrait. Cite [S1], sans autre référence."},
                {"role": "user", "content": f"Extrait [S1] : {passages[top]} Question : Où et quand a lieu la permanence Iris ?"},
            ],
        }
        llm_start = time.perf_counter()
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions", json=payload,
                headers={"Authorization": "Bearer " + key, "User-Agent": "assistant-rag-step0/1.0"}, timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            raise HTTPException(502, "llm_probe_failed") from None
        references = re.findall(r"\[S\d+\]", answer)
        references_valid = bool(references) and set(references) == {"[S1]"}
        facts_valid = all(s in answer.lower() for s in ["b214", "mardi", "14", "16"])
        finish_reason = result["choices"][0].get("finish_reason")
        passed = bool(references_valid and facts_valid and finish_reason == "stop")
        return {
            "status": "passed" if passed else "failed",
            "runtime": "vercel-container" if os.environ.get("VERCEL") else "local",
            "region": os.environ.get("VERCEL_REGION"),
            "embedding": {"model": MODEL_ID, "revision": REVISION, "dimensions": 384, "normalized": bool(shape_valid), "retrieved_expected_source": top == 0, "load_seconds": round(load_seconds, 3), "encode_seconds": round(embeddings_seconds, 3)},
            "llm": {"provider": "Groq", "model": payload["model"], "http_status": response.status_code, "citations_valid": references_valid, "factual_check_passed": facts_valid, "finish_reason": finish_reason, "usage": result.get("usage"), "latency_seconds": round(time.perf_counter() - llm_start, 3), "rate_limits": {name: response.headers.get(name) for name in ["x-ratelimit-limit-requests", "x-ratelimit-limit-tokens"]}},
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "total_seconds": round(time.perf_counter() - start, 3),
        }


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Assistant RAG — prototype</title><body><main><h1>Assistant RAG</h1><p>Prototype de qualification de l’étape 0 sur Vercel.</p><p>FastAPI, embeddings E5 sur CPU et appel Groq depuis un extrait fictif.</p><p>Les essais de génération sont réservés au contrôle serveur. L’application V1 reste à développer.</p><a href="/health">État du service</a></main></body></html>"""


@app.get("/health")
def health():
    return {"status": "ok", "scope": "step0-synthetic-probe"}


@app.post("/probe")
def probe(authorization: str | None = Header(default=None)):
    token = os.environ.get("STEP0_PROBE_TOKEN")
    if not token:
        raise HTTPException(503, "probe_disabled")
    if not secrets.compare_digest((authorization or "").encode(), ("Bearer " + token).encode()):
        raise HTTPException(401, "unauthorized")
    return run_probe()
