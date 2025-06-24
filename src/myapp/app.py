import os
from fastapi import FastAPI
from myapp.api_routes import router
from  myapp.database import init_db


api = FastAPI()
api.include_router(router)
init_db()
