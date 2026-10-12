"""Synthetic HTTP provider, only exposed inside the isolated local test profile."""

import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

if os.environ.get("LLM_TEST_ONLY") != "assistant_rag_test":
    raise RuntimeError("Test-only provider requires an explicit isolated environment")

app = FastAPI()
mode = "answered"
calls = 0
release = asyncio.Event()


@app.post("/control")
async def control(request: Request) -> dict[str, int | str]:
    global mode, calls
    body = await request.json()
    if body.get("release"):
        release.set()
    else:
        mode = body.get("mode", "answered")
        calls = 0
        release.clear()
    return {"mode": mode, "calls": calls}


@app.get("/control")
async def status() -> dict[str, int | str]:
    return {"mode": mode, "calls": calls}


@app.post("/openai/v1/chat/completions")
async def generate(request: Request) -> JSONResponse:
    global calls
    payload: dict[str, Any] = await request.json()
    calls += 1
    if mode == "pause":
        await asyncio.wait_for(release.wait(), timeout=14)
    if mode == "quota":
        return JSONResponse(
            {"error": "synthetic quota"}, status_code=429, headers={"retry-after": "60"}
        )
    sources = json.loads(payload["messages"][-1]["content"].split("SOURCES\n", 1)[1])
    content = {
        "state": "answered",
        "claims": [
            {
                "text": "Le lancement a lieu à Lyon.",
                "evidence": [
                    {"source_id": "S99" if mode == "invalid" else sources[0]["id"], "quote": "Lyon"}
                ],
            }
        ],
    }
    if mode == "iris":
        follow_up = (
            "chevauchement" in payload["messages"][-1]["content"].split("SOURCES\n", 1)[0].lower()
        )
        quote = "40 tokens" if follow_up else "220 tokens"
        source = next(item for item in sources if quote in item["text"])
        content = {
            "state": "answered",
            "claims": [
                {
                    "text": f"Le chevauchement est de {quote}."
                    if follow_up
                    else f"La taille des passages est de {quote}.",
                    "evidence": [{"source_id": source["id"], "quote": quote}],
                }
            ],
        }
    if mode == "absent":
        content = {"state": "insufficient_context", "claims": []}
    return JSONResponse(
        {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 50},
        }
    )
