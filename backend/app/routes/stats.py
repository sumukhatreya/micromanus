"""GET /api/stats — per-thread usage & cost breakdown (PLAN.md §B6).

Aggregates `usage_logs` (one row per agent LLM call) into one row per thread,
joined to `threads` for the title. Each row carries the token split
(input / output / cached), that split priced per the model used, and the total
cost. Grand totals across all the caller's threads accompany them so the
frontend can render summary cards (total spend, total tokens, chats count).

Everything is scoped to the JWT-derived user_id — never a user_id from the
request (PLAN.md §B1 notes). supabase-py has no group-by, so we fetch the
caller's rows and aggregate in Python; fine at this project's scale.
"""

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.models_config import find_model
from app.supabase_client import get_supabase

router = APIRouter(prefix="/api", tags=["stats"])


def _category_costs(log: dict) -> dict:
    """Split one usage_log's cost into input / cached / output USD.

    Mirrors compute_cost in llm.py: cached_tokens is a subset of input_tokens
    (served from the provider's prompt cache), so uncached input is billed at
    the input rate and the cached portion at the cheaper cached rate. Prices are
    per 1M tokens. If the model id is unknown (e.g. removed from the config),
    fall back to the stored total on the output line so nothing is lost.
    """
    input_tokens = log.get("input_tokens") or 0
    output_tokens = log.get("output_tokens") or 0
    cached_tokens = min(log.get("cached_tokens") or 0, input_tokens)
    uncached_input = input_tokens - cached_tokens

    info = find_model(log.get("model") or "")
    if info is None:
        return {"input": 0.0, "cached": 0.0, "output": float(log.get("cost_usd") or 0)}

    price = info["price"]
    return {
        "input": uncached_input * price["input"] / 1_000_000,
        "cached": cached_tokens * price["cached_input"] / 1_000_000,
        "output": output_tokens * price["output"] / 1_000_000,
    }


@router.get("/stats")
def get_stats(user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()

    logs = (
        supabase.table("usage_logs")
        .select(
            "thread_id, model, input_tokens, output_tokens, cached_tokens, cost_usd"
        )
        .eq("user_id", user.user_id)
        .execute()
        .data
        or []
    )

    # Titles for the threads referenced by those logs.
    titles = {
        t["id"]: t["title"]
        for t in (
            supabase.table("threads")
            .select("id, title")
            .eq("user_id", user.user_id)
            .execute()
            .data
            or []
        )
    }

    threads: dict[str, dict] = {}
    for log in logs:
        tid = log["thread_id"]
        row = threads.get(tid)
        if row is None:
            row = threads[tid] = {
                "thread_id": tid,
                "title": titles.get(tid, "(deleted chat)"),
                "models": set(),
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cost_input": 0.0,
                "cost_cached": 0.0,
                "cost_output": 0.0,
                "cost_usd": 0.0,
                "runs": 0,
            }

        info = find_model(log.get("model") or "")
        row["models"].add(info["label"] if info else (log.get("model") or "unknown"))
        row["input_tokens"] += log.get("input_tokens") or 0
        row["output_tokens"] += log.get("output_tokens") or 0
        row["cached_tokens"] += min(
            log.get("cached_tokens") or 0, log.get("input_tokens") or 0
        )
        costs = _category_costs(log)
        row["cost_input"] += costs["input"]
        row["cost_cached"] += costs["cached"]
        row["cost_output"] += costs["output"]
        row["cost_usd"] += log.get("cost_usd") or 0
        row["runs"] += 1

    # Finalize: sets → sorted lists, round money, newest-highest-cost first.
    thread_rows = []
    for row in threads.values():
        row["models"] = sorted(row["models"])
        for k in ("cost_input", "cost_cached", "cost_output", "cost_usd"):
            row[k] = round(row[k], 6)
        thread_rows.append(row)
    thread_rows.sort(key=lambda r: r["cost_usd"], reverse=True)

    totals = {
        "input_tokens": sum(r["input_tokens"] for r in thread_rows),
        "output_tokens": sum(r["output_tokens"] for r in thread_rows),
        "cached_tokens": sum(r["cached_tokens"] for r in thread_rows),
        "cost_usd": round(sum(r["cost_usd"] for r in thread_rows), 6),
        "thread_count": len(thread_rows),
        "run_count": sum(r["runs"] for r in thread_rows),
    }
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]

    return {"threads": thread_rows, "totals": totals}
