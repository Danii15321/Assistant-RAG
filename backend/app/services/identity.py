from collections.abc import Callable
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError


class InvalidIdentity(Exception):
    pass


class IdentityUnavailable(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    session_id: str


class TrustedKeySource:
    def __init__(self, url: str) -> None:
        self.client = PyJWKClient(url, timeout=3, lifespan=300)

    def __call__(self, token: str) -> Ed25519PublicKey:
        try:
            key = self.client.get_signing_key_from_jwt(token).key
            if not isinstance(key, Ed25519PublicKey):
                raise InvalidIdentity
            return key
        except PyJWKClientConnectionError as error:
            raise IdentityUnavailable from error
        except PyJWKClientError as error:
            raise InvalidIdentity from error


class TokenVerifier:
    def __init__(
        self, issuer: str, audience: str, key_source: Callable[[str], Ed25519PublicKey]
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.key_source = key_source

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            if len(token) > 8192:
                raise InvalidIdentity
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "EdDSA" or not isinstance(header.get("kid"), str):
                raise InvalidIdentity
            claims = jwt.decode(
                token,
                self.key_source(token),
                algorithms=["EdDSA"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["sub", "sid", "iss", "aud", "exp", "iat"]},
            )
            subject, session_id = claims["sub"], claims["sid"]
            if not isinstance(subject, str) or not 1 <= len(subject) <= 128:
                raise InvalidIdentity
            if not isinstance(session_id, str) or not 1 <= len(session_id) <= 128:
                raise InvalidIdentity
            return VerifiedIdentity(subject, session_id)
        except PyJWTError as error:
            raise InvalidIdentity from error
