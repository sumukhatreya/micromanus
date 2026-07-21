"""LLM providers, model IDs, and pricing (PLAN.md §B4).

Single source of truth for the BYOK model picker and (Phase 5) usage-cost
computation. The frontend fetches the public shape via GET /api/models.

All three providers are driven through the OpenAI Python SDK by swapping
`base_url` (PLAN.md §B4):
    openai     → https://api.openai.com/v1        (native)
    anthropic  → https://api.anthropic.com/v1/    (OpenAI-compat endpoint)
    kimi       → https://api.moonshot.ai/v1       (natively OpenAI-compatible)

Pricing is USD per 1,000,000 tokens, split into:
    input         — uncached prompt tokens (cache-miss)
    cached_input  — prompt tokens served from the provider's prompt cache
    output        — completion tokens
Cost is then (uncached_input x input_cost) + (cached_input x cached_cost) + (output x output_cost) (PLAN.md §B4 caching section).

============================================================================
MODEL IDS AND PRICES VERIFIED VIA WEB SEARCH ON 2026-07-21.
Sources: provider pricing pages (OpenAI, Anthropic, Moonshot) as aggregated by
silicondata.com / benchlm.ai, plus Anthropic's published per-token rates.
Providers change models and prices often — re-verify before relying on these.
Anthropic cached-input = 0.1x input (standard cache-read rate). Anthropic's
OpenAI-compat layer has limited caching, so cached_tokens is often 0 there
(PLAN.md §B4) — the cached_input rate is still listed for when it is non-zero.
============================================================================
"""

# provider key -> {label, base_url, models: [{id, label, price:{input,cached_input,output}}]}
PROVIDERS: dict = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [
            {
                "id": "gpt-5",
                "label": "GPT-5",
                "price": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
            },
            {
                "id": "gpt-5-mini",
                "label": "GPT-5 mini",
                "price": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
            },
            {
                "id": "gpt-4.1",
                "label": "GPT-4.1",
                "price": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
            },
            {
                "id": "gpt-4o",
                "label": "GPT-4o",
                "price": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
            },
        ],
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1/",
        "models": [
            {
                "id": "claude-opus-4-8",
                "label": "Claude Opus 4.8",
                "price": {"input": 5.00, "cached_input": 0.50, "output": 25.00},
            },
            {
                "id": "claude-sonnet-5",
                "label": "Claude Sonnet 5",
                "price": {"input": 3.00, "cached_input": 0.30, "output": 15.00},
            },
            {
                "id": "claude-haiku-4-5",
                "label": "Claude Haiku 4.5",
                "price": {"input": 1.00, "cached_input": 0.10, "output": 5.00},
            },
        ],
    },
    "kimi": {
        "label": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.ai/v1",
        "models": [
            {
                "id": "kimi-k2.6",
                "label": "Kimi K2.6",
                "price": {"input": 0.95, "cached_input": 0.16, "output": 4.00},
            },
            {
                "id": "kimi-k2.5",
                "label": "Kimi K2.5",
                "price": {"input": 0.60, "cached_input": 0.10, "output": 3.00},
            },
            {
                "id": "kimi-k2.7-code",
                "label": "Kimi K2.7 Code",
                "price": {"input": 0.95, "cached_input": 0.19, "output": 4.00},
            },
        ],
    },
}


def public_providers() -> list[dict]:
    """Shape for GET /api/models — providers with their models, no secrets."""
    return [
        {
            "provider": key,
            "label": p["label"],
            "models": [
                {"id": m["id"], "label": m["label"], "price": m["price"]}
                for m in p["models"]
            ],
        }
        for key, p in PROVIDERS.items()
    ]


def is_valid(provider: str, model: str) -> bool:
    """True if `model` is a known model id for `provider`."""
    p = PROVIDERS.get(provider)
    if not p:
        return False
    return any(m["id"] == model for m in p["models"])


def get_base_url(provider: str) -> str | None:
    p = PROVIDERS.get(provider)
    return p["base_url"] if p else None


def get_pricing(provider: str, model: str) -> dict | None:
    """Return {input, cached_input, output} per 1M tokens, or None if unknown."""
    p = PROVIDERS.get(provider)
    if not p:
        return None
    for m in p["models"]:
        if m["id"] == model:
            return m["price"]
    return None
