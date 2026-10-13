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
        self.cookies = http.cookiejar.MozillaCookieJar()

    def request(self, method, path, data=None, *, origin=None, extra_headers=None):
        headers = {"content-type": "application/json", "origin": origin or self.base}
        headers.update(extra_headers or {})
        if self.oidc:
            headers["x-vercel-trusted-oidc-idp-token"] = self.oidc
        start = time.monotonic()
        # Explicit IPv4 and bounded connect timeout avoid WSL TLS stalls. curl
        # does not follow redirects; credentials stay on the exact app origin.
        with tempfile.TemporaryDirectory(prefix="rag-http-") as directory:
            cookie_path = str(Path(directory) / "cookies")
            body_path = Path(directory) / "body"
            self.cookies.save(cookie_path, ignore_discard=True, ignore_expires=True)
            configuration = ["url = " + json.dumps(self.base + path)]
            configuration.extend("header = " + json.dumps(k + ": " + v) for k, v in headers.items())
            if data is not None or method == "POST":
                configuration.append("data = " + json.dumps(json.dumps(data if data is not None else {})))
            result = subprocess.run(["curl", "--ipv4", "--silent", "--config", "-",
                "--request", method, "--cookie", cookie_path, "--cookie-jar", cookie_path,
                "--connect-timeout", "15", "--max-time", "190", "--output", str(body_path),
                "--write-out", "%{http_code}"], input="\n".join(configuration) + "\n",
                capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError("Qualification transport failed; request must be reconciled (curl " + str(result.returncode) + ")")
            status = int(result.stdout)
            if 300 <= status < 400:
                raise RuntimeError("Redirect refused; credentials remain scoped")
            self.cookies.clear()
            self.cookies.load(cookie_path, ignore_discard=True, ignore_expires=True)
            raw = body_path.read_bytes()
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = {"code": "non_json_response"}
        return status, payload, round(1000 * (time.monotonic() - start), 2)

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
