"""Service-role Supabase client (PLAN.md §B0).

The backend is the only thing that touches Postgres, and it does so with the
`service_role` key — RLS is off, so every query MUST be scoped to the
authenticated user_id from the JWT (see app/auth.py). Import `get_supabase()`
wherever DB access is needed; the client is created lazily and reused.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env"
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
