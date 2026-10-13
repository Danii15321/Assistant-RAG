"""Qualification client: private cookies/state, redacted errors, public fixtures only."""
import http.cookiejar
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "evaluation/.qa"
REPORTS = ROOT / "evaluation/reports"


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        source, target = urlparse(request.full_url), urlparse(newurl)
        if (source.scheme, source.netloc) != (target.scheme, target.netloc):
            raise RuntimeError("Cross-origin redirect refused; credentials remain scoped")
        return super().redirect_request(request, response, code, message, headers, newurl)


class Client:
    def __init__(self, base, account, oidc=None):
        parsed = urlparse(base)
        if parsed.scheme != "https" or not parsed.hostname.endswith(".vercel.app"):
            raise ValueError("Qualification requires a Vercel HTTPS deployment")
        self.base, self.account, self.oidc = base.rstrip("/"), account, oidc
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies), SameOriginRedirect())

    def request(self, method, path, data=None, *, origin=None, extra_headers=None):
        headers = {"content-type": "application/json", "origin": origin or self.base}
        headers.update(extra_headers or {})
        if self.oidc:
            headers["x-vercel-trusted-oidc-idp-token"] = self.oidc
        request = urllib.request.Request(self.base + path,
            data=json.dumps(data).encode() if data is not None else b"{}" if method == "POST" else None,
            headers=headers, method=method)
        start = time.monotonic()
        try:
            response = self.opener.open(request, timeout=190)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = {"code": "non_json_response"}
        return response.status, payload, round(1000 * (time.monotonic() - start), 2)

    def login(self):
        code, _, _ = self.request("POST", "/api/auth/sign-in/username", self.account)
        if code != 200:
            raise RuntimeError("Cloud sign-in failed: " + str(code))

    def signup(self):
        code, _, _ = self.request("POST", "/api/auth/sign-up/username", self.account)
        if code != 200:
            raise RuntimeError("Cloud sign-up failed: " + str(code))

    def upload(self, filename, raw, mime):
        status, value, _ = self.request("POST", "/api/v1/documents/uploads",
            {"filename": filename, "size_bytes": len(raw), "content_type": mime})
        if status != 201:
            raise RuntimeError("Reservation failed: " + str(status) + " " + str(value))
        url = value["upload_url"]
        # Never send application cookies, credentials or OIDC to Blob.
        # curl streams large bodies reliably on WSL; the capability is stdin-only.
        with tempfile.TemporaryDirectory(prefix="rag-qualification-") as directory:
            original = Path(directory) / "original"
            original.write_bytes(raw)
            original.chmod(0o600)
            result = subprocess.run([
                "curl", "--silent", "--config", "-", "--upload-file", str(original),
                "--header", "Content-Type: " + mime, "--max-time", "120",
                "--output", "/dev/null", "--write-out", "%{http_code}",
            ], input="url = " + json.dumps(url) + "\n", text=True, capture_output=True)
            if result.returncode or result.stdout not in {"200", "201", "204"}:
                raise RuntimeError("Direct Blob upload failed: " + result.stdout[:3])
        status, document, _ = self.request("POST", "/api/v1/documents", {"upload_id": value["document"]["id"]})
        if status not in (200, 202):
            raise RuntimeError("Finalization failed: " + str(status) + " " + str(document))
        return document

    def wait_document(self, identifier, expected="ready"):
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            status, document, _ = self.request("GET", "/api/v1/documents/" + identifier)
            if status != 200:
                raise RuntimeError("Document read failed: " + str(status))
            if document["state"] == expected:
                return document
            if document["state"] == "failed":
                raise RuntimeError("Document processing failed: " + str(document["error_code"]))
            time.sleep(2)
        raise RuntimeError("Document processing timed out")


def save_private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    path.chmod(0o600)
