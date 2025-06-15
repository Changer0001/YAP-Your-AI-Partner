import os
from fastapi import FastAPI
from myapp.api_routes import router

api = FastAPI()
api.include_router(router)
