import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.api_routes import router         # ✅ updated import path
from app.db.database import init_db           # ✅ updated import path

print("🚀 FastAPI app loaded!")

app = FastAPI(
    title="YAP - Your AI Partner",
    version="1.0.0"
)

# Include API routes
app.include_router(router)

# Initialize DB at startup
@app.on_event("startup")
def on_startup():
    init_db()

# Global 422 Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": (await request.body()).decode("utf-8")
        }
    )
