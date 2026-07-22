"""LLM client wiring and usage-cost computation (PLAN.md §B4/§B5).

One OpenAI-SDK client serves every provider by swapping `base_url` (see
models_config). The "active key" is simply the caller's most-recently-saved
api_keys row (PLAN.md §B4). Cost is computed from the per-1M-token prices in
models_config against the `usage` object returned on each completion.
"""

from dataclasses import dataclass

from openai import OpenAI

from app.crypto import decrypt
from app.models_config import get_base_url, get_pricing
from app.supabase_client import get_supabase


@dataclass
class ActiveKey:
    provider: str
    model: str
    api_key: str  # plaintext, in-process only


def get_active_key(user_id: str) -> ActiveKey | None:
    """The user's latest saved key (active key), decrypted, or None if they
    haven't added one yet."""
    supabase = get_supabase()
    res = (
        supabase.table("api_keys")
        .select("provider, model, encrypted_key")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]
    return ActiveKey(
        provider=row["provider"],
        model=row["model"],
        api_key=decrypt(row["encrypted_key"]),
    )


def build_client(active: ActiveKey) -> OpenAI:
    """OpenAI SDK client pointed at the provider's base_url."""
    base_url = get_base_url(active.provider)
    if not base_url:
        raise ValueError(f"Unknown provider: {active.provider}")
    return OpenAI(api_key=active.api_key, base_url=base_url)


@dataclass
class UsageCost:
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float


def compute_cost(provider: str, model: str, usage) -> UsageCost:
    """Turn a completion's `usage` object into token counts + USD cost.

    `cached_tokens` is a subset of `prompt_tokens` (the provider served them from
    its prompt cache), so uncached input = prompt_tokens − cached_tokens. Prices
    are per 1,000,000 tokens. Missing fields default to 0 — some providers (e.g.
    Anthropic's compat layer) omit cached-token details entirely (PLAN.md §B4).
    """
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = 0
    if details is not None:
        # details may be a pydantic object or a plain dict depending on provider.
        if isinstance(details, dict):
            cached_tokens = details.get("cached_tokens", 0) or 0
        else:
            cached_tokens = getattr(details, "cached_tokens", 0) or 0

    cached_tokens = min(cached_tokens, prompt_tokens)
    uncached_input = prompt_tokens - cached_tokens

    price = get_pricing(provider, model) or {"input": 0, "cached_input": 0, "output": 0}
    cost = (
        uncached_input * price["input"]
        + cached_tokens * price["cached_input"]
        + completion_tokens * price["output"]
    ) / 1_000_000

    return UsageCost(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=round(cost, 6),
    )
