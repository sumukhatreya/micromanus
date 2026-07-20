"""GET /api/me — the caller's profile (PLAN.md §B2).

The frontend uses this as the single source of truth for route gating
(login → paywall → app): the `unlocked` flag decides whether the user can reach
the app or is bounced to the paywall.
"""

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.supabase_client import get_supabase

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
def get_me(user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    res = (
        supabase.table("profiles")
        .select("id, credits, unlocked, unlock_method")
        .eq("id", user.user_id)
        .limit(1)
        .execute()
    )

    if res.data:
        return res.data[0]

    # Defensive fallback: the profiles trigger normally runs on signup, but a
    # brand-new session could momentarily race it. Return safe defaults (locked,
    # zero credits) rather than 500 — the frontend keeps the user on the paywall.
    return {
        "id": user.user_id,
        "credits": 0,
        "unlocked": False,
        "unlock_method": None,
    }
