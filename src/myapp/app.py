import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from myapp.api_routes import router
from myapp.database import init_db
print("🚀 FastAPI app loaded!")
api = FastAPI()

# Include API routes
api.include_router(router)

# Initialize DB at startup
@api.on_event("startup")
def on_startup():
    init_db()

# Global 422 Validation Error Handler
@api.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": (await request.body()).decode("utf-8")
        }
    )
