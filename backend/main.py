"""IT Copilot — FastAPI application entrypoint.

Local-first: binds to localhost by default, uses only local models/storage, serves the SPA, and
requires authentication for all data endpoints. Run with:

    uvicorn backend.main:app --host 127.0.0.1 --port 8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import admin
from backend.routers import auth as auth_router
from backend.routers import chat, documents, integrations, search, system
from backend.services import auth as auth_service
from backend.services import registry

logger = logging.getLogger("it_copilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.init_db()
    auth_service.init_db()
    yield


app = FastAPI(title="IT Copilot", version="1.1.0",
              description="Local, private IT knowledge base powered by Qwen 2.5 3B.",
              lifespan=lifespan)

# Local UI only. The SPA is same-origin; localhost origins allowed for dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    # Log server-side (never the document/message contents); return a generic message.
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "IT Copilot", "mode": "local"}


# Public auth endpoints.
app.include_router(auth_router.router)

# All data endpoints require a valid session token.
_auth = [Depends(auth_service.require_auth)]
app.include_router(chat.router, dependencies=_auth)
app.include_router(documents.router, dependencies=_auth)
app.include_router(search.router, dependencies=_auth)
app.include_router(system.router, dependencies=_auth)
app.include_router(integrations.router, dependencies=_auth)
# Admin-only endpoints — require the admin role on every route.
app.include_router(admin.router, dependencies=[Depends(auth_service.require_admin)])

# Serve the frontend SPA (mounted last so /api/* wins). html=True serves index.html.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
