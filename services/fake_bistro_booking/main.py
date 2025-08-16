# main.py (fake bistro booking service with Stripe Test Mode)
import os, uuid
from datetime import datetime, date, time, timedelta
from typing import List, Optional
import stripe
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime
from dateutil import tz
from pydantic_settings import BaseSettings, SettingsConfigDict  # <-- add SettingsConfigDict

class Settings(BaseSettings):
    # strings
    STRIPE_API_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:9000"
    BUSINESS_NAME: str = "ACME Bistro"
    TIMEZONE: str = "America/Los_Angeles"
    BOOKING_DB_URL: str = "sqlite:///./bookings.db"

    # ints
    OPEN_HOUR: int = 10
    CLOSE_HOUR: int = 22
    SLOT_MINUTES: int = 60
    MAX_BOOKINGS_PER_SLOT: int = 5
    DEPOSIT_CENTS_PER_GUEST: int = 1000  # $10 ea

    # 👇 tell pydantic-settings to read from a .env file in this folder
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY

class Base(DeclarativeBase): pass

class BookingStatus:
    PENDING = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"

class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    party_size: Mapped[int] = mapped_column(Integer)
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String, default=BookingStatus.PENDING)
    checkout_session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payment_intent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

engine = create_engine(settings.BOOKING_DB_URL, echo=False, future=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

LOCAL_TZ = tz.gettz(settings.TIMEZONE)
def local_to_utc(dt_local: datetime) -> datetime:
    if dt_local.tzinfo is None: dt_local = dt_local.replace(tzinfo=LOCAL_TZ)
    return dt_local.astimezone(tz.UTC).replace(tzinfo=None)
def utc_to_local(dt_utc: datetime) -> datetime:
    if dt_utc.tzinfo is None: dt_utc = dt_utc.replace(tzinfo=tz.UTC)
    return dt_utc.astimezone(LOCAL_TZ)
def slots_for_date(d: date) -> List[datetime]:
    start = datetime.combine(d, time(hour=settings.OPEN_HOUR)).replace(tzinfo=LOCAL_TZ)
    end   = datetime.combine(d, time(hour=settings.CLOSE_HOUR)).replace(tzinfo=LOCAL_TZ)
    slots, cur = [], start
    delta = timedelta(minutes=settings.SLOT_MINUTES)
    while cur < end: slots.append(cur); cur += delta
    return slots

class AvailabilityIn(BaseModel):
    date: str
    party_size: int = Field(ge=1, le=20)
class AvailabilityOut(BaseModel):
    date: str; timezone: str; slots: List[str]
class BookIn(BaseModel):
    datetime: str; party_size: int = Field(ge=1, le=20); name: str; email: str; phone: str
class BookOut(BaseModel):
    booking_id: str; status: str; checkout_url: Optional[str] = None
class CancelIn(BaseModel): booking_id: str

app = FastAPI(title="Fake Bistro Booking API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"ok": True, "business": settings.BUSINESS_NAME}

@app.post("/availability", response_model=AvailabilityOut)
def availability(payload: AvailabilityIn):
    try: d = datetime.fromisoformat(payload.date).date()
    except: raise HTTPException(400, "Invalid date; use YYYY-MM-DD")
    slots = []
    with SessionLocal() as db:
        for dt_local in slots_for_date(d):
            start_utc = local_to_utc(dt_local)
            count = db.execute(
                select(func.count()).select_from(Booking).where(
                    Booking.start_utc == start_utc, Booking.status == BookingStatus.CONFIRMED
                )
            ).scalar_one()
            if count < settings.MAX_BOOKINGS_PER_SLOT:
                slots.append(dt_local.replace(tzinfo=None).isoformat())
    return AvailabilityOut(date=payload.date, timezone=settings.TIMEZONE, slots=slots)

@app.post("/book", response_model=BookOut)
def book(payload: BookIn, request: Request):
    try: dt_local = datetime.fromisoformat(payload.datetime)
    except: raise HTTPException(400, "Invalid datetime; use local ISO format")
    with SessionLocal() as db:
        start_utc = local_to_utc(dt_local)
        confirmed = db.execute(
            select(func.count()).select_from(Booking).where(
                Booking.start_utc == start_utc, Booking.status == BookingStatus.CONFIRMED
            )
        ).scalar_one()
        if confirmed >= settings.MAX_BOOKINGS_PER_SLOT:
            raise HTTPException(409, "Slot full, pick another time")
        b = Booking(
            id=str(uuid.uuid4()), name=payload.name, email=payload.email, phone=payload.phone,
            party_size=payload.party_size, start_utc=start_utc, status=BookingStatus.PENDING
        )
        db.add(b); db.commit()

        checkout_url = None
        if settings.STRIPE_API_KEY:
            amount = settings.DEPOSIT_CENTS_PER_GUEST * payload.party_size
            try:
                session = stripe.checkout.Session.create(
                    mode="payment",
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount,
                            "product_data": {
                                "name": f"{settings.BUSINESS_NAME} Reservation Deposit",
                                "description": f"{payload.party_size} guests on {dt_local.isoformat()} {settings.TIMEZONE}"
                            },
                        },
                        "quantity": 1,
                    }],
                    success_url=f"{settings.PUBLIC_BASE_URL}/thanks?booking_id={b.id}",
                    cancel_url=f"{settings.PUBLIC_BASE_URL}/canceled?booking_id={b.id}",
                    metadata={"booking_id": b.id},
                )
                b.checkout_session_id = session.get("id")
                checkout_url = session.get("url")
                db.add(b); db.commit()
            except Exception:
                pass  # keep pending without checkout link
        return BookOut(booking_id=b.id, status=b.status, checkout_url=checkout_url)

@app.get("/bookings/{booking_id}")
def get_booking(booking_id: str):
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        if not b: raise HTTPException(404, "Not found")
        return {
            "id": b.id, "status": b.status, "name": b.name, "email": b.email, "phone": b.phone,
            "party_size": b.party_size,
            "start_local": utc_to_local(b.start_utc).replace(tzinfo=None).isoformat(),
            "start_utc": b.start_utc.isoformat(),
            "checkout_session_id": b.checkout_session_id,
            "payment_intent_id": b.payment_intent_id,
        }

@app.post("/cancel")
def cancel(payload: CancelIn):
    with SessionLocal() as db:
        b = db.get(Booking, payload.booking_id)
        if not b: raise HTTPException(404, "Not found")
        if b.status == BookingStatus.CONFIRMED and settings.STRIPE_API_KEY and b.payment_intent_id:
            try: stripe.Refund.create(payment_intent=b.payment_intent_id)
            except Exception: pass
        b.status = BookingStatus.CANCELED; db.add(b); db.commit()
        return {"booking_id": b.id, "status": b.status}

@app.post("/confirm/{booking_id}")
def confirm_manual(booking_id: str):
    with SessionLocal() as db:
        b = db.get(Booking, booking_id)
        if not b: raise HTTPException(404, "Not found")
        b.status = BookingStatus.CONFIRMED; db.add(b); db.commit()
        return {"ok": True, "booking_id": b.id, "status": b.status}

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(400, "Webhook secret not configured")
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig, secret=settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = session.get("metadata", {}).get("booking_id")
        pi = session.get("payment_intent")
        if booking_id:
            with SessionLocal() as db:
                b = db.get(Booking, booking_id)
                if b:
                    b.status = BookingStatus.CONFIRMED
                    b.payment_intent_id = pi
                    db.add(b); db.commit()
    return {"received": True}
