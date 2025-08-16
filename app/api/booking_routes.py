# app/api/booking_routes.py
import os, requests
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

# Adjust import path if yours differs
from app.api.auth import verify_token

BOOKING_API_BASE = os.getenv("BOOKING_API_BASE", "http://localhost:9000")

router = APIRouter(prefix="/book", tags=["booking"])

class AvailabilityIn(BaseModel):
    date: str                 # "YYYY-MM-DD"
    party_size: int = Field(ge=1, le=20)

class AvailabilityOut(BaseModel):
    date: str
    timezone: str
    slots: List[str]          # ISO local times, e.g. "2025-08-20T19:00:00"

class BookIn(BaseModel):
    datetime: str             # "YYYY-MM-DDTHH:MM:SS" (local business time)
    party_size: int = Field(ge=1, le=20)
    name: str
    email: str
    phone: str

class BookOut(BaseModel):
    booking_id: str
    status: str
    checkout_url: Optional[str] = None

def _post(path: str, payload: dict, timeout: int = 15):
    url = f"{BOOKING_API_BASE}{path}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Booking service unavailable: {e}")

# booking_routes.py
@router.post("/availability", response_model=AvailabilityOut)
def get_availability(body: AvailabilityIn, user=Depends(verify_token)):
    return _post("/availability", body.model_dump())

@router.post("/create", response_model=BookOut)
def create_booking(body: BookIn, user=Depends(verify_token)):
    return _post("/book", body.model_dump())


@router.get("/status/{booking_id}")
def booking_status(booking_id: str, user=Depends(verify_token)):
    url = f"{BOOKING_API_BASE}/bookings/{booking_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Booking service unavailable: {e}")
