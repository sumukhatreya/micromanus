"""Application settings, loaded from environment / backend/.env.

All secrets are optional at this scaffolding stage so the app boots without a
populated .env. Later phases (auth, paywall, BYOK) will require real values.
See PLAN.md §B8 for the full variable list.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase (Phase 2+)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Fernet key for encrypting stored API keys (Phase 4)
    encryption_key: str = ""

    # Stripe test mode (Phase 3)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Web search (Phase 5)
    tavily_api_key: str = ""

    # Frontend origin — used for CORS and Stripe redirects
    frontend_url: str = "http://localhost:5173"


settings = Settings()
