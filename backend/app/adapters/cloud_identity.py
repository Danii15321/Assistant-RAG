"""Vercel runtime identity is request-scoped and may rotate without a restart."""

import os
from contextvars import ContextVar
from pathlib import Path

request_oidc: ContextVar[str | None] = ContextVar("request_oidc", default=None)


def deployment_headers() -> dict[str, str]:
    token = request_oidc.get()
    if not token:
        file = os.environ.get("VERCEL_OIDC_TOKEN_FILE")
        token = Path(file).read_text().strip() if file else os.environ.get("VERCEL_OIDC_TOKEN")
    return {"x-vercel-trusted-oidc-idp-token": token} if token else {}
