import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/internal", tags=["internal"])


def authorize(request: Request) -> None:
    settings = request.app.state.settings
    secret = settings.internal_worker_secret
    if (
        not settings.cloud_runtime
        or secret is None
        or not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + secret.get_secret_value()
        )
    ):
        raise HTTPException(404, "Not found")


@router.post("/work")
def work(request: Request) -> dict[str, bool]:
    authorize(request)
    if request.headers.get("x-reconcile") == "1":
        request.app.state.cloud_worker.reconcile()
    return {"pending": request.app.state.cloud_worker.drain()}


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    authorize(request)
    process = request.app.state.cloud_worker.indexer.encoder.process
    paths = [Path("/proc/self/status")]
    if process is not None and process.poll() is None:
        paths.append(Path(f"/proc/{process.pid}/status"))
    kib = 0
    for path in paths:
        for line in path.read_text().splitlines():
            if line.startswith("VmRSS:"):
                kib += int(line.split()[1])
    return {"resident_mib": round(kib / 1024, 2), "model_loaded": len(paths) == 2}
