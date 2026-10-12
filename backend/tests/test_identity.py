from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.identity import InvalidIdentity, TokenVerifier

ISSUER = "http://localhost:3000"
AUDIENCE = "assistant-rag-api"
KEY = Ed25519PrivateKey.generate()


def token(**changes: object) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "alice",
        "sid": "session-alice",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(changes)
    return jwt.encode(payload, KEY, algorithm="EdDSA", headers={"kid": "trusted"})


def verifier() -> TokenVerifier:
    return TokenVerifier(ISSUER, AUDIENCE, lambda _: KEY.public_key())


def test_valid_signed_identity() -> None:
    identity = verifier().verify(token())
    assert (identity.subject, identity.session_id) == ("alice", "session-alice")


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "another-api"},
        {"exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        {"iat": datetime.now(timezone.utc) + timedelta(minutes=10)},
        {"sub": ""},
        {"sid": ""},
        {"sid": 123},
    ],
)
def test_invalid_claims_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidIdentity):
        verifier().verify(token(**changes))


def test_tampered_signature_and_unsigned_tokens_are_rejected() -> None:
    bad_key = Ed25519PrivateKey.generate()
    forged = jwt.encode(
        jwt.decode(token(), options={"verify_signature": False}),
        bad_key,
        algorithm="EdDSA",
        headers={"kid": "trusted"},
    )
    for candidate in [
        forged,
        "malformed",
        "a" * 9000,
        jwt.encode({"sub": "alice"}, "", algorithm="none"),
    ]:
        with pytest.raises(InvalidIdentity):
            verifier().verify(candidate)


@pytest.mark.parametrize("candidate", [None, "tampered", "expired", "revoked"])
def test_private_api_rejects_invalid_sessions(candidate: str | None) -> None:
    from fastapi.testclient import TestClient

    from app.api.identity import get_repository
    from app.config import Settings
    from app.main import create_app

    class Repository:
        def session_is_active(self, identity: object) -> bool:
            return candidate != "revoked"

    app = create_app(Settings(database_url=None))
    app.dependency_overrides[get_repository] = lambda: Repository()
    with TestClient(app) as client:
        app.state.token_verifier = verifier()
        value = (
            token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))
            if candidate == "expired"
            else token()
        )
        if candidate == "tampered":
            value = "tampered"
        headers = {} if candidate is None else {"Authorization": f"Bearer {value}"}
        result = client.get("/api/v1/users/me", headers=headers)
        assert result.status_code == 401
        assert result.headers["www-authenticate"] == "Bearer"


def test_unavailable_keys_are_sanitized() -> None:
    from fastapi.testclient import TestClient

    from app.api.identity import get_repository
    from app.config import Settings
    from app.main import create_app
    from app.services.identity import IdentityUnavailable

    def failed_keys(_: str) -> Ed25519PrivateKey:
        raise IdentityUnavailable("private-password and internal-host")

    app = create_app(Settings(database_url=None))
    app.dependency_overrides[get_repository] = lambda: object()
    with TestClient(app) as client:
        app.state.token_verifier = TokenVerifier(ISSUER, AUDIENCE, failed_keys)
        result = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token()}"})
        assert result.status_code == 503
        assert "private-password" not in result.text
