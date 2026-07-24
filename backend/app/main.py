"""Minimus FastAPI application entrypoint.

Phase 1 scaffold: health route + CORS. Feature routes land in later phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import chat, keys, me, models, paywall, stats

app = FastAPI(title="Minimus API")

# CORS restricted to the frontend origin + local Vite dev server (PLAN.md §B8).
allowed_origins = list({settings.frontend_url, "http://localhost:5173"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(me.router)
app.include_router(paywall.router)
app.include_router(models.router)
app.include_router(keys.router)
app.include_router(chat.router)
app.include_router(stats.router)
