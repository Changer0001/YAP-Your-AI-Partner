from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.api_routes import router
from app.db.database import init_db

app = FastAPI(
    title="YAP - Your AI Partner",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Mount at root. If you prefer /api prefix, change to: app.include_router(router, prefix="/api")
app.include_router(router)

@app.get("/_health")
def health():
    return {"ok": True}

@app.on_event("startup")
def on_startup():
    init_db()
    # Dump routes at startup so you can copy the exact paths
    for r in app.routes:
        if isinstance(r, APIRoute):
            print(f"{list(r.methods)} {r.path}")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": (await request.body()).decode("utf-8")}
    )
