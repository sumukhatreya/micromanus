"""Paywall: coupon redemption + Stripe test-mode checkout (PLAN.md §B3).

Three endpoints:
  * POST /api/paywall/redeem-coupon          (auth) — unlock via the coupon code
  * POST /api/paywall/create-checkout-session (auth) — start a Stripe Checkout
  * POST /api/stripe/webhook                 (NO auth) — Stripe → us; the request
        is authenticated by its signature, not a JWT.

Credit rule (PLAN.md §B3): unlocking grants 5 credits. Coupon sets credits to 5
(one unlock per user, enforced by the 409); Stripe adds 5 per completed payment.
All money/credit writes go through the service-role client and are scoped to the
user id we trust — the JWT `sub` for coupons, the session's `client_reference_id`
(which we set ourselves) for Stripe.
"""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["paywall"])

# The one valid coupon (PLAN.md §A5/§B3). Compared exactly, server-side.
COUPON_CODE = "USE_MINIMUS"

# Credits granted per unlock.
UNLOCK_CREDITS = 5

stripe.api_key = settings.stripe_secret_key


# ---------------------------------------------------------------------------
# Coupon redemption
# ---------------------------------------------------------------------------
@router.post("/paywall/redeem-coupon")
def redeem_coupon(body: dict, user: CurrentUser = Depends(get_current_user)):
    code = (body or {}).get("code", "")
    supabase = get_supabase()

    profile = (
        supabase.table("profiles")
        .select("id, credits, unlocked, unlock_method")
        .eq("id", user.user_id)
        .limit(1)
        .execute()
    )
    current = profile.data[0] if profile.data else None

    if current and current.get("unlocked"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already unlocked"
        )

    if code != COUPON_CODE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid coupon"
        )

    updated = (
        supabase.table("profiles")
        .update(
            {
                "unlocked": True,
                "unlock_method": "coupon",
                "credits": UNLOCK_CREDITS,
            }
        )
        .eq("id", user.user_id)
        .execute()
    )

    # Record the redemption (user_id is PK → one row per user). Upsert keeps this
    # idempotent if it somehow runs twice.
    supabase.table("coupon_redemptions").upsert(
        {"user_id": user.user_id, "code": code}
    ).execute()

    return updated.data[0] if updated.data else {"unlocked": True, "credits": UNLOCK_CREDITS}


# ---------------------------------------------------------------------------
# Stripe Checkout Session
# ---------------------------------------------------------------------------
@router.post("/paywall/create-checkout-session")
def create_checkout_session(user: CurrentUser = Depends(get_current_user)):
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured on the server",
        )

    frontend = settings.frontend_url.rstrip("/")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": 500,  # $5.00 in cents
                        "product_data": {"name": "Minimus — 5 credits"},
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=user.user_id,
            success_url=f"{frontend}/paywall?status=success",
            cancel_url=f"{frontend}/paywall?status=cancel",
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {exc.user_message or str(exc)}",
        ) from exc
    return {"url": session.url}


# ---------------------------------------------------------------------------
# Stripe webhook (unauthenticated — the signature is the auth)
# ---------------------------------------------------------------------------
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        # Bad payload or wrong signing secret (PLAN.md pitfall #4).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        ) from exc
    if event["type"] == "checkout.session.completed":
        # _fulfill_checkout does blocking (sync) supabase I/O. This handler is
        # async (needed for `await request.body()`), so run the blocking work in
        # a threadpool rather than stalling the event loop.
        await run_in_threadpool(_fulfill_checkout, event)

    # Always 200 other event types so Stripe stops retrying them.
    return {"received": True}


def _fulfill_checkout(event: dict) -> None:
    """Grant credits for a completed checkout, exactly once per event."""
    supabase = get_supabase()
    event_id = event["id"]

    # Idempotency: claim this event id first. Stripe retries deliveries, so a
    # re-delivered event conflicts on the primary key and we skip it.
    already_processed = (
        supabase.table("stripe_events")
        .select("id")
        .eq("id", event_id)
        .limit(1)
        .execute()
    )
    if already_processed.data:
        return
    
    supabase.table("stripe_events").insert({"id": event_id}).execute()

    session = event["data"]["object"]
    user_id = session["client_reference_id"]
    if not user_id:
        # A completed checkout we can't attribute to a user. Retrying won't fix
        # this, so we still return 200 — but it must not pass silently.
        logger.warning(
            "checkout.session.completed with no client_reference_id (event %s, "
            "session %s) — payment not credited",
            event_id,
            session.get("id"),
        )
        return

    profile = (
        supabase.table("profiles")
        .select("credits")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not profile.data:
        # "Can't happen" (signup trigger creates the profile), but if it does the
        # update below would no-op silently. Log so a lost payment is visible.
        logger.warning(
            "checkout.session.completed for unknown profile %s (event %s) — "
            "payment not credited",
            user_id,
            event_id,
        )
        return
    current_credits = profile.data[0]["credits"]

    supabase.table("profiles").update(
        {
            "unlocked": True,
            "unlock_method": "stripe",
            "credits": current_credits + UNLOCK_CREDITS,
        }
    ).eq("id", user_id).execute()
