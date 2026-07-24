"""Chat + threads endpoints and the agent-run entrypoint (PLAN.md §B5).

  * GET  /api/threads                 list the caller's threads (sidebar)
  * POST /api/threads                 create a new thread
  * GET  /api/threads/{id}/messages   messages for a thread (also the poll target)
  * POST /api/chat                    persist the user message, spend 1 credit,
                                      run the agent loop, return the answer

POST /api/chat is a sync def on purpose: the agent loop does blocking I/O
(OpenAI SDK, Tavily, Supabase), so FastAPI runs it in a threadpool and the 1.5s
GET /messages polls from the frontend are served concurrently — that's what
makes tool_event steps appear live while a run is in progress (PLAN.md §B5).

Every query is scoped to the JWT-derived user_id; a thread the caller doesn't
own returns 404, never another user's data (PLAN.md §B1 notes).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from openai import APIError, APIConnectionError, AuthenticationError
from pydantic import BaseModel

from app.agent import run_agent
from app.auth import CurrentUser, get_current_user
from app.llm import build_client, get_active_key
from app.supabase_client import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


class NewThreadBody(BaseModel):
    title: str | None = None


class ChatBody(BaseModel):
    thread_id: str | None = None
    message: str


def _title_from(message: str) -> str:
    title = message.strip().replace("\n", " ")[:40]
    return title or "New chat"


def _get_owned_thread(supabase, thread_id: str, user_id: str) -> dict:
    res = (
        supabase.table("threads")
        .select("id, title, user_id")
        .eq("id", thread_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return res.data[0]


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------
@router.get("/threads")
def list_threads(user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    res = (
        supabase.table("threads")
        .select("id, title, created_at")
        .eq("user_id", user.user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def create_thread(body: NewThreadBody, user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    title = _title_from(body.title) if body.title else "New chat"
    res = (
        supabase.table("threads")
        .insert({"user_id": user.user_id, "title": title})
        .execute()
    )
    return res.data[0]


@router.get("/threads/{thread_id}/messages")
def get_messages(thread_id: str, user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    _get_owned_thread(supabase, thread_id, user.user_id)
    res = (
        supabase.table("messages")
        .select("id, role, content, artifact_url, artifact_title, created_at")
        .eq("thread_id", thread_id)
        .order("created_at")
        .execute()
    )
    return res.data or []


# ---------------------------------------------------------------------------
# Cancel — abort a running agent loop
# ---------------------------------------------------------------------------
@router.post("/threads/{thread_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_thread(thread_id: str, request: Request):
    """Fire-and-forget cancel via navigator.sendBeacon (no auth header).

    sendBeacon sends a plain POST with no Authorization header and the body as a
    Blob, so we skip JWT auth and use the thread_id alone.  The agent loop
    checks the cancelled flag each iteration and stops early.
    """
    supabase = get_supabase()
    supabase.table("threads").update({"cancelled": True}).eq("id", thread_id).execute()
    return None


# ---------------------------------------------------------------------------
# Chat — run the agent
# ---------------------------------------------------------------------------
def _friendly_llm_error(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return (
            "Your API key was rejected by the provider. Check the key in Settings "
            "and try again."
        )
    if isinstance(exc, APIConnectionError):
        return "Couldn't reach the model provider. Please try again in a moment."
    if isinstance(exc, APIError):
        # Includes rate limits, bad model ids, provider-side errors.
        message = getattr(exc, "message", None) or str(exc)
        return f"The model provider returned an error: {message}"
    return "Something went wrong while running the agent. Please try again."


@router.post("/chat")
def chat(body: ChatBody, user: CurrentUser = Depends(get_current_user)):
    message = body.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required"
        )

    supabase = get_supabase()

    # Gate: must be unlocked and have credits (PLAN.md §B2/§B3).
    profile_res = (
        supabase.table("profiles")
        .select("credits, unlocked")
        .eq("id", user.user_id)
        .limit(1)
        .execute()
    )
    profile = profile_res.data[0] if profile_res.data else None
    if not profile or not profile.get("unlocked"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Account is locked"
        )
    if (profile.get("credits") or 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="You're out of credits.",
        )

    # Must have an API key before we spend a credit (PLAN.md §A5 #6).
    active = get_active_key(user.user_id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add your API key in Settings to start chatting.",
        )

    # Resolve / create the thread.
    if body.thread_id:
        thread = _get_owned_thread(supabase, body.thread_id, user.user_id)
        thread_id = thread["id"]
        # Give an untitled thread a title from its first message.
        if thread["title"] == "New chat":
            supabase.table("threads").update({"title": _title_from(message)}).eq(
                "id", thread_id
            ).execute()
    else:
        created = (
            supabase.table("threads")
            .insert({"user_id": user.user_id, "title": _title_from(message)})
            .execute()
        )
        thread_id = created.data[0]["id"]

    # Persist the user message, then spend the credit before the run starts.
    supabase.table("messages").insert(
        {"thread_id": thread_id, "role": "user", "content": message}
    ).execute()

    new_credits = profile["credits"] - 1
    lock_status = False if new_credits == 0 else True
    supabase.table("profiles").update({"credits": new_credits, "unlocked": lock_status}).eq(
        "id", user.user_id
    ).execute()

    # Run the agent. On a hard failure (e.g. bad key) refund the credit so the
    # user isn't charged for a run that produced nothing, and surface a clean
    # error rather than a 500 (PLAN.md §A5 #6).
    try:
        client = build_client(active)
        final_message = run_agent(user.user_id, thread_id, active, client)
    except Exception as exc:
        logger.warning("Agent run failed for thread %s: %s", thread_id, exc)
        supabase.table("profiles").update({"credits": profile["credits"], "unlocked": True}).eq(
            "id", user.user_id
        ).execute()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_friendly_llm_error(exc),
        ) from exc

    return {
        "thread_id": thread_id,
        "credits": new_credits,
        "message": final_message,
    }
