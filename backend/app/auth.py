"""Supabase JWT authentication (PLAN.md §B2, pitfall #5).

Supabase projects sign access tokens one of two ways:
  * Legacy static secret  → HS256, verified with the project's JWT secret.
  * New signing keys       → ES256 / RS256, verified with the public key from
                             the project's JWKS endpoint.
We detect which by reading the token's unverified `alg` header and handle both,
so this works whether or not the project has migrated to asymmetric keys.
"""

import ssl
from dataclasses import dataclass

import certifi
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# Supabase issues tokens with the audience claim "authenticated".
_AUDIENCE = "authenticated"

# PyJWKClient fetches the JWKS over HTTPS via urllib, which needs a CA bundle to
# validate the certificate. Standalone Python builds (macOS, minimal containers)
# often ship without one, so point the SSL context at certifi's bundle — portable
# across the local machine and the deploy host.
_ssl_context = ssl.create_default_context(cafile=certifi.where())

# JWKS discovery endpoint for asymmetric (ES256/RS256) signing keys. PyJWKClient
# caches the fetched public keys; safe to construct once at import time.
_jwks_client: jwt.PyJWKClient | None = None
if settings.supabase_url:
    _jwks_client = jwt.PyJWKClient(
        f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
        ssl_context=_ssl_context,
    )

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class CurrentUser:
    user_id: str
    email: str | None = None


def _decode(token: str) -> dict:
    """Verify the token signature/claims and return its payload, or raise."""
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError as exc:  # malformed token
        raise _UNAUTHORIZED from exc

    common = {"audience": _AUDIENCE, "options": {"require": ["sub"]}}

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise _UNAUTHORIZED
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **common,
            )
        except jwt.PyJWTError as exc:
            raise _UNAUTHORIZED from exc

    # Asymmetric signing keys (ES256 / RS256) → verify via JWKS public key.
    if _jwks_client is None:
        raise _UNAUTHORIZED
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            **common,
        )
    except jwt.PyJWTError as exc:
        raise _UNAUTHORIZED from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """FastAPI dependency: validate the Supabase JWT and return the caller."""
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    payload = _decode(credentials.credentials)
    return CurrentUser(user_id=payload["sub"], email=payload.get("email"))
