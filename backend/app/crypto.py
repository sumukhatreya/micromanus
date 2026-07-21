"""Fernet encryption for stored API keys (PLAN.md §B4).

BYOK keys are encrypted with a symmetric Fernet key (`ENCRYPTION_KEY` in
backend/.env, generated once) before they touch the database, and decrypted
only in-process when a request needs the plaintext (masking for display now;
the agent loop in Phase 5). The key never leaves the backend.

Generate a key once with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY must be set in backend/.env (a Fernet key). Generate "
            'one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    # Fernet accepts the urlsafe-base64 key as str or bytes.
    return Fernet(settings.encryption_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext API key; returns a Fernet token (str) for storage."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a stored Fernet token back to the plaintext API key."""
    return _fernet().decrypt(token.encode()).decode()


def mask(api_key: str) -> str:
    """Display form of a key — never return the full secret to the client.

    Shows enough to recognize the key (prefix + last 4) without exposing it,
    e.g. 'sk-pr...a1b2'. Short keys collapse to just the tail.
    """
    if len(api_key) <= 8:
        return "…" + api_key[-2:] if api_key else ""
    return f"{api_key[:5]}…{api_key[-4:]}"
