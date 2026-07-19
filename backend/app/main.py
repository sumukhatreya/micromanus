"""MicroManus FastAPI application entrypoint.

Phase 1 scaffold: health route + CORS. Feature routes land in later phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="MicroManus API")

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
