"""GET /api/models — the provider + model catalog for the picker (PLAN.md §B4).

Returns the public model list with pricing (no secrets) so the Settings page
can populate its provider/model dropdowns. Auth-gated for consistency with the
rest of /api; the frontend already sends the JWT on every call.
"""

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, get_current_user
from app.models_config import public_providers

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
def get_models(user: CurrentUser = Depends(get_current_user)):
    return public_providers()
