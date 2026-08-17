"""IT Copilot — FastAPI application entrypoint.

Local-first: binds to localhost by default, uses only local models/storage, and
serves the single-page frontend. Run with:

    uvicorn backend.main:app --host 127.0.0.1 --port 8000
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import chat, documents, search, system
from backend.services import registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.init_db()  # idempotent; registry also self-initialises on import
    yield


app = FastAPI(title="IT Copilot", version="1.0.0",
              description="Local, private IT knowledge base powered by Qwen 2.5 3B.",
              lifespan=lifespan)

# Local UI only. Same-origin in normal use; localhost origins allowed for dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "IT Copilot", "mode": "local"}


app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(system.router)

# Serve the frontend SPA (mounted last so /api/* wins). html=True serves index.html.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
