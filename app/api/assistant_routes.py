import os, re, requests
from datetime import date, timedelta, datetime
from typing import Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.auth import verify_token  # your existing auth

BOOKING_API_BASE = os.getenv("BOOKING_API_BASE", "http://127.0.0.1:9000")
router = APIRouter(prefix="/assistant", tags=["assistant"])

# ---------- helpers ----------
def _post(path: str, body: dict, to=15):
    r = requests.post(f"{BOOKING_API_BASE}{path}", json=body, timeout=to)
    if r.status_code >= 400: raise HTTPException(r.status_code, r.text)
    return r.json()

def _get(path: str, to=10):
    r = requests.get(f"{BOOKING_API_BASE}{path}", timeout=to)
    if r.status_code >= 400: raise HTTPException(r.status_code, r.text)
    return r.json()

def _nearest_slot(slots, desired: Optional[Tuple[int,int]]):
    if not slots: return None
    if not desired: return slots[0]
    want = desired[0]*60 + desired[1]
    best, diff = None, 10**9
    for s in slots:
        dt = datetime.fromisoformat(s); mins = dt.hour*60 + dt.minute
        d = abs(mins - want)
        if d < diff: diff, best = d, s
    return best or slots[0]

# tiny intent parser (same logic we prototyped in UI)
CONFIRM_WORDS = {
    "yes","yep","yeah","book it","go ahead","please book",
    "sounds good","do it","confirm","ok","okay","sure","let's do it"
}
PAID_WORDS = {"paid","i paid","done","finished payment","completed payment","payment done"}

def _parse(text: str):
    t = (text or "").lower().strip()
    intent = None
    if any(k in t for k in ["availability","available","open","free","check"]): intent = "availability"
    if any(k in t for k in ["book","reserve"]): intent = "book"
    if any(k in t for k in ["pay","payment","checkout"]): intent = "pay"
    if any(k in t for k in ["status","booking id"]): intent = "status"
    if any(w in t for w in CONFIRM_WORDS): intent = intent or "book"
    if any(w in t for w in PAID_WORDS): intent = "status"

    # party
    m = re.search(r"(?:for|of)\s+(\d{1,2})\b", t)
    party = int(m.group(1)) if m else None

    # date
    d = None
    if "tomorrow" in t: d = date.today() + timedelta(days=1)
    elif "today" in t:  d = date.today()

    # time
    mt = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    hhmm = None
    if mt:
        hh = int(mt.group(1)); mm = int(mt.group(2) or 0); ap = (mt.group(3) or "").lower()
        if ap == "pm" and hh < 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59: hhmm = (hh, mm)

    return {"intent": intent, "party": party, "date": d, "time": hhmm}

# ---------- schema ----------
class ChatIn(BaseModel):
    text: str
    party: Optional[int] = None
    booking_id: Optional[str] = None
    candidate_slot: Optional[str] = None  # ISO local

class ChatOut(BaseModel):
    reply: str
    booking_id: Optional[str] = None
    checkout_url: Optional[str] = None
    candidate_slot: Optional[str] = None

# ---------- endpoint ----------
@router.post("/message", response_model=ChatOut)
def message(body: ChatIn, user=Depends(verify_token)):
    p = _parse(body.text)
    party = p["party"] or body.party or 2
    the_date = p["date"] or (date.today() + timedelta(days=1))

    # AVAILABILITY
    if p["intent"] in (None, "availability"):
        avail = _post("/availability", {"date": the_date.isoformat(), "party_size": party})
        slots = avail.get("slots", []); tz = avail.get("timezone", "local")
        if not slots:
            return ChatOut(reply=f"Sorry, no openings on **{the_date}**.")
        best = _nearest_slot(slots, p["time"])
        human = datetime.fromisoformat(best).strftime("%a %b %d at %I:%M %p")
        return ChatOut(
            reply=f"I can do **{human}** ({tz}) for **{party}**. Want me to book it?",
            candidate_slot=best
        )

    # BOOK
    if p["intent"] == "book":
        slot = body.candidate_slot
        if not slot:
            avail = _post("/availability", {"date": the_date.isoformat(), "party_size": party})
            slots = avail.get("slots", [])
            if not slots:
                return ChatOut(reply=f"Sorry, no slots on **{the_date}**.")
            slot = _nearest_slot(slots, p["time"])
        created = _post("/book", {
            "datetime": slot, "party_size": party,
            "name":"Alex","email":"alex@example.com","phone":"555-0100"
        })
        human = datetime.fromisoformat(slot).strftime("%a %b %d at %I:%M %p")
        if created.get("checkout_url"):
            return ChatOut(
                reply=(f"Held **{human}** for **{party}**. "
                       f"Pay deposit to confirm:\n{created['checkout_url']}\n"
                       f"Say **paid** or **status** when done."),
                booking_id=created["booking_id"],
                checkout_url=created["checkout_url"],
                candidate_slot=slot
            )
        return ChatOut(
            reply=(f"Hold created for **{human}** (party {party}). "
                   f"It’s **pending**. Say **status** to check."),
            booking_id=created["booking_id"],
            candidate_slot=slot
        )

    # PAY (really: status + link)
    if p["intent"] == "pay":
        if not body.booking_id:
            return ChatOut(reply="I don’t have a booking yet. Ask me to book a time first.")
        s = _get(f"/bookings/{body.booking_id}")
        if s.get("status") == "confirmed":
            when = datetime.fromisoformat(s["start_local"]).strftime("%a %b %d at %I:%M %p")
            return ChatOut(reply=f"All set ✅ — **confirmed** for **{when}** (party {s['party_size']}).")
        return ChatOut(
            reply=f"Still **{s['status']}**. Use your Stripe checkout link to finish, then say **paid**.",
            booking_id=body.booking_id
        )

    # STATUS
    if p["intent"] == "status":
        if not body.booking_id:
            return ChatOut(reply="I don’t have a booking id yet. Ask me to book a time first.")
        s = _get(f"/bookings/{body.booking_id}")
        when = datetime.fromisoformat(s["start_local"]).strftime("%a %b %d at %I:%M %p")
        if s["status"] == "confirmed":
            return ChatOut(reply=f"Booking `{body.booking_id}` is **confirmed** ✅ — **{when}**, party {s['party_size']}.")
        return ChatOut(reply=f"Booking `{body.booking_id}` is **{s['status']}** — **{when}**, party {s['party_size']}.")

    # fallback
    return ChatOut(reply="How can I help — check availability, book, pay, or status?")
