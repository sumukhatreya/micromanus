"""BYOK API-key management (PLAN.md §B4).

  * POST   /api/keys       add a key (provider + model + api_key), Fernet-encrypted
  * GET    /api/keys       list the caller's keys — provider, model, MASKED key
  * DELETE /api/keys/{id}  remove one of the caller's keys

The plaintext key is never returned once stored; GET returns a masked form.
"latest saved key = active key" (PLAN.md §B4) — the agent loop (Phase 5) picks
the most-recently-created key. Every query is scoped to the JWT-derived
user_id; a user_id is never trusted from the request body (PLAN.md §B1 notes).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user
from app.crypto import encrypt, mask, decrypt
from app.models_config import is_valid
from app.supabase_client import get_supabase

router = APIRouter(prefix="/api", tags=["keys"])


class AddKeyBody(BaseModel):
    provider: str
    model: str
    api_key: str


def _public_row(row: dict) -> dict:
    """DB row -> client shape: masked key, never the ciphertext or plaintext."""
    try:
        masked = mask(decrypt(row["encrypted_key"]))
    except Exception:
        # A key encrypted under a different ENCRYPTION_KEY (e.g. key rotated)
        # can't be decrypted. Don't 500 the whole list — show it as unusable.
        masked = "unavailable"
    return {
        "id": row["id"],
        "provider": row["provider"],
        "model": row["model"],
        "masked_key": masked,
        "created_at": row.get("created_at"),
    }


@router.get("/keys")
def list_keys(user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    res = (
        supabase.table("api_keys")
        .select("id, provider, model, encrypted_key, created_at")
        .eq("user_id", user.user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_public_row(r) for r in (res.data or [])]


@router.post("/keys", status_code=status.HTTP_201_CREATED)
def add_key(body: AddKeyBody, user: CurrentUser = Depends(get_current_user)):
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="API key is required"
        )
    if not is_valid(body.provider, body.model):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown provider or model. Pick one from the list.",
        )

    supabase = get_supabase()
    inserted = (
        supabase.table("api_keys")
        .insert(
            {
                "user_id": user.user_id,
                "provider": body.provider,
                "model": body.model,
                "encrypted_key": encrypt(api_key),
            }
        )
        .execute()
    )
    return _public_row(inserted.data[0])


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(key_id: str, user: CurrentUser = Depends(get_current_user)):
    supabase = get_supabase()
    # Scope by user_id so a caller can only delete their own keys.
    deleted = (
        supabase.table("api_keys")
        .delete()
        .eq("id", key_id)
        .eq("user_id", user.user_id)
        .execute()
    )
    if not deleted.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Key not found"
        )
    # 204: no body.
