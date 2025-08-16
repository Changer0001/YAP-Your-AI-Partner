# app/api/api_routes.py
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
import logging, json, re, os, requests
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime, date, timedelta

from app.db.database import get_db
from app.api.auth import verify_token, register_user, authenticate_user
from app.core.utils import get_user_id
from app.db.chat_store import save_chat_history, get_user_history, get_recent_history
from app.llm.llm_interface import ask_llm_hf, ask_llm_hf_stream, format_history_blocks
from app.retriever.rrf_hyde import build_context_from_collection
from app.api.booking_routes import router as booking_router
from app.api.assistant_routes import router as assistant_router

# ───────────────── Router init ─────────────────
router = APIRouter()
router.include_router(booking_router)
router.include_router(assistant_router)
logging.basicConfig(level=logging.INFO)

# ---------- Lightweight lexical small-talk detector (to bypass RAG gate) ----------
_GREETING_RX  = re.compile(r"\b(hi|hey|hello|good (morning|afternoon|evening))\b", re.I)
_THANKS_RX    = re.compile(r"\b(thanks|thank you|appreciate(d)?|much appreciated)\b", re.I)
_GOODBYE_RX   = re.compile(r"\b(bye|good night|see you|take care)\b", re.I)
_HOWAREYOU_RX = re.compile(r"\b(how (are|r) (you|u)|how’s it going|how are things)\b", re.I)

def _is_smalltalk_text(text: str) -> bool:
    t = (text or "").strip()
    return bool(
        _GREETING_RX.search(t) or _THANKS_RX.search(t) or _GOODBYE_RX.search(t) or _HOWAREYOU_RX.search(t)
    )

# ---------- Simple lexical relevance gate for RAG ----------
_STOP = set(
    "a an the and or but if while to for of on in at from by with as into over under between "
    "this that those these is are was were be been being do does did so such it its we our you your they their".split()
)

def _tok(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']+", (s or "").lower()) if w not in _STOP and len(w) > 2}

def _ctx_relevance(question: str, rows) -> float:
    """
    Quick lexical relevance between the question and the top retrieved text chunks.
    rows is expected to be a list of tuples: (rid, text, meta)
    """
    q = _tok(question)
    if not q:
        return 0.0
    top_text = " ".join((text or "") for (_, text, _) in (rows[:3] if rows else []))
    c = _tok(top_text)
    if not c:
        return 0.0
    # coverage of question terms by context
    return len(q & c) / len(q)

# ───────────────── Server-side booking chat (LLM-free) ─────────────────
BOOKING_API_BASE = os.getenv("BOOKING_API_BASE", "http://localhost:9000").rstrip("/")

def _post_booking(path: str, payload: dict, timeout: int = 15):
    try:
        r = requests.post(f"{BOOKING_API_BASE}{path}", json=payload, timeout=timeout)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Booking service unavailable: {e}")

def _get_booking(path: str, timeout: int = 10):
    try:
        r = requests.get(f"{BOOKING_API_BASE}{path}", timeout=timeout)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Booking service unavailable: {e}")

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
CS_RE   = re.compile(r"\bcs_[A-Za-z0-9]+")
PI_RE   = re.compile(r"\bpi_[A-Za-z0-9]+")

def _mask_email(email: str) -> str:
    try:
        u, d = email.split("@", 1)
        return (u[0] + "***@" + d) if len(u) > 1 else ("***@" + d)
    except Exception:
        return "***"

def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def _mask_phone(phone: str) -> str:
    last4 = _digits(phone)[-4:] if _digits(phone) else ""
    return f"***-***-{last4}" if last4 else "***"

def _fmt_dt(iso_local: str) -> str:
    try:
        return datetime.fromisoformat(iso_local).strftime("%a, %b %d, %Y %I:%M %p")
    except Exception:
        return iso_local

def _fmt_when(iso_local: str) -> str:
    try:
        return datetime.fromisoformat(iso_local).strftime("%a %b %d at %I:%M %p")
    except Exception:
        return iso_local
# ── Confirmation / Decline detectors + "is this phrased as a question?" ──
CONFIRM_RX = re.compile(r"\b(confirm|book\s+it|go\s*ahead|yes|yep|yeah|ok(?:ay)?|please\s*book|do\s+it|sounds\s+good)\b", re.I)
DECLINE_RX = re.compile(r"\b(no|don['’]?t|do not|stop|cancel|change)\b", re.I)

def _is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.endswith("?") or t.startswith(("can i", "could i", "may i", "is there", "do you have"))

def _format_booking_reply(b: dict) -> str:
    return (
        f"Booking **{b.get('id','')}** is **{b.get('status','unknown')}**.\n\n"
        f"- Name: {b.get('name','')}\n"
        f"- Party size: {b.get('party_size','')}\n"
        f"- When: {_fmt_dt(b.get('start_local',''))}\n"
        f"- Contact: {_mask_email(b.get('email',''))}, {_mask_phone(b.get('phone',''))}\n"
    )

CHAT_STATE: Dict[str, Dict[str, Any]] = defaultdict(dict)  # user_id -> simple dialog state

def _parse_booking_intent(text: str):
    t = (text or "").lower().strip()
    intent = None
    if any(k in t for k in ["availability", "available"]) or ("check" in t and "availability" in t):
        intent = "availability"
    elif "status" in t or "booking id" in t:
        intent = "status"
    elif any(k in t for k in ["pay", "payment", "checkout"]):
        intent = "pay"
    elif any(k in t for k in ["book", "reserve", "confirm"]):
        intent = "book"

    # party: "for 2" / "party of 4"
    m_party = re.search(r"(?:for|of)\s+(\d{1,2})", t)
    party = int(m_party.group(1)) if m_party else None

    # date: today/tomorrow
    if "tomorrow" in t: d = date.today() + timedelta(days=1)
    elif "today" in t:  d = date.today()
    else:               d = None

    # time: "7pm"/"19:00"
    m_time = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    hhmm = None
    if m_time:
        hh = int(m_time.group(1)); mm = int(m_time.group(2) or 0); ap = (m_time.group(3) or "").lower()
        if ap == "pm" and hh < 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59: hhmm = (hh, mm)

    # explicit UUID
    uuid = None
    m_uuid = UUID_RE.search(text or "")
    if m_uuid: uuid = m_uuid.group(0)

    is_booking = (intent is not None) or (uuid is not None)
    return {"intent": intent if is_booking else None, "party": party, "date": d, "time": hhmm, "uuid": uuid,"question": _is_question(text)}

def _nearest_slot(slots, desired_hhmm):
    if not slots: return None
    if not desired_hhmm: return slots[0]
    want = desired_hhmm[0]*60 + desired_hhmm[1]
    best, diff = None, 10**9
    for s in slots:
        dt = datetime.fromisoformat(s); mins = dt.hour*60 + dt.minute
        d = abs(mins - want)
        if d < diff: diff, best = d, s
    return best or slots[0]

def maybe_route_booking_chat(user_id: str, user_text: str) -> Optional[dict]:
    
    """
    Full booking flow (LLM-free): availability → book (Stripe) → pay → status.
    Returns {'answer': str, 'sources': []} when handled; else None.
    """
    p = _parse_booking_intent(user_text)
    if not p["intent"] and not p["uuid"]:
        return None  # not a booking conversation

    state = CHAT_STATE[user_id]
    confirm = bool(CONFIRM_RX.search(user_text or ""))
    decline = bool(DECLINE_RX.search(user_text or ""))

    # 0) direct status by pasted UUID
    if p["uuid"] and (p["intent"] in (None, "status", "book", "pay")):
        b = _get_booking(f"/bookings/{p['uuid']}")
        state.update({"booking_id": b["id"]})
        return {"answer":
            (f"Booking **{b['id']}** is **{b['status']}**.\n\n"
             f"- Party: {b['party_size']}\n"
             f"- When: {_fmt_when(b['start_local'])}\n"
             f"- Payment intent: `{b.get('payment_intent_id','—')}`"),
            "sources": []}

    # 1) availability
    if p["intent"] == "availability":
        party = p["party"] or state.get("party")
        d     = p["date"]  or state.get("date") or (date.today() + timedelta(days=1))
        if not party:
            return {"answer": "Sure—what party size?", "sources": []}
        avail = _post_booking("/availability", {"date": d.strftime("%Y-%m-%d"), "party_size": party})
        slots = avail.get("slots", [])
        if not slots:
            return {"answer": f"Sorry, no open slots on **{d}**.", "sources": []}
        best = _nearest_slot(slots, p["time"])
        state.update({"party": party, "date": d, "time": p["time"], "slot": best})
        return {"answer": f"Nearest time on **{d}** (TZ {avail.get('timezone','local')}): **{_fmt_when(best)}**. Say **book it** to reserve.", "sources": []}

    # 2) book / confirm
    if p["intent"] in ("book", "confirm"):
        party = p["party"] or state.get("party")
        d     = p["date"]  or state.get("date")
        slot  = state.get("slot")

        # If the user declines while something is pending
        if decline and slot:
            state.clear()
            return {"answer": "Okay, I won’t book it. Want a different time or party size?", "sources": []}

        # If there is no pending slot yet OR the user asked as a question,
        # just PROPOSE a slot and ask for confirmation — do NOT create a booking.
        if (not slot) or p.get("question", False):
            missing = []
            if not party: missing.append("party size")
            if not d:     missing.append("date")
            if not (p["time"] or slot): missing.append("time")
            if missing:
                return {"answer": "Sure—before I hold a table, I need your " + ", ".join(missing) + ".", "sources": []}

            avail = _post_booking("/availability", {"date": d.strftime("%Y-%m-%d"), "party_size": party})
            slots = avail.get("slots", [])
            if not slots:
                return {"answer": f"Sorry, no open slots on **{d}**.", "sources": []}
            slot = _nearest_slot(slots, p["time"])
            state.update({"party": party, "date": d, "time": p["time"], "slot": slot})
            return {"answer": f"I can hold **{_fmt_when(slot)}** for **{party}**. "
                            f"Say **confirm** (or *book it*) and I’ll reserve it.", "sources": []}

        # We already have a pending slot — only create the booking if the user confirms
        if not confirm:
            return {"answer": f"I’m holding **{_fmt_when(slot)}** for **{party}**. "
                            f"Say **confirm** to book, or **cancel** to discard.", "sources": []}

        # ✅ Confirmed → create the booking now
        created = _post_booking("/book", {
            "datetime":  slot,
            "party_size": party,
            "name":  "Customer",
            "email": "customer@example.com",
            "phone": "000-000-0000",
        })
        state.update({"booking_id": created["booking_id"], "checkout_url": created.get("checkout_url")})
        state.pop("slot", None)  # no longer pending

        if created.get("checkout_url"):
            return {"answer": (f"Booked! ID `{created['booking_id']}`. "
                            f"[Pay deposit]({created['checkout_url']}) to confirm, then say **status**."),
                    "sources": []}
        return {"answer": f"Booking created as pending. ID `{created['booking_id']}`. Say **status** to check.", "sources": []}
    # 3) pay
    if p["intent"] == "pay":
        if not state.get("booking_id"):
            return {"answer": "I don’t have a booking yet. Ask me to book a time first.", "sources": []}
        if state.get("checkout_url"):
            return {"answer": f"Open the Stripe checkout link to pay: {state['checkout_url']}  \nAfter paying, say **status**.", "sources": []}
        b = _get_booking(f"/bookings/{state['booking_id']}")
        if b.get("status") == "confirmed":
            return {"answer": f"Already confirmed ✅. Booking `{b['id']}`.", "sources": []}
        return {"answer": "I don’t see a checkout link saved. Try creating a new booking.", "sources": []}

    # 4) status
    if p["intent"] == "status":
        if not state.get("booking_id"):
            return {"answer": "I don’t have a booking id yet. Ask me to book a time first.", "sources": []}
        b = _get_booking(f"/bookings/{state['booking_id']}")
        return {"answer": (f"Booking `{b['id']}` • {_fmt_when(b['start_local'])} • party {b['party_size']}\n"
                           f"**Status:** **{b['status']}**  \nPayment intent: `{b.get('payment_intent_id','—')}`"),
                "sources": []}

    return None

def maybe_handle_booking_intent(user_text: str) -> Optional[dict]:
    """
    Minimal helper for:
      • “which one is booking id” (distinguish UUID vs Stripe IDs)
      • “status/check/lookup ... <UUID>” or pasted UUID only
    (This is kept for clarity responses; main flow uses maybe_route_booking_chat.)
    """
    text = (user_text or "")
    low  = text.lower()

    # 1) Identify which token is the "booking id"
    if "booking id" in low and ("which" in low or "which one" in low):
        uuids = UUID_RE.findall(text)
        cs    = CS_RE.findall(text)
        pi    = PI_RE.findall(text)
        if uuids:
            return {"answer": (
                f"The booking ID is the UUID: **{uuids[0]}**.\n\n"
                f"- `cs_…` = Stripe **checkout_session_id**\n"
                f"- `pi_…` = Stripe **payment_intent_id**"
            )}
        if cs or pi:
            return {"answer": (
                "I don’t see a UUID here. The **booking ID** is the long UUID (e.g., `0319…`).\n"
                "`cs_…` and `pi_…` are Stripe IDs (checkout session and payment intent)."
            )}

    # 2) Direct status via UUID
    uuid_m = UUID_RE.search(text)
    if uuid_m and any(k in low for k in ("status", "check", "lookup", "booking", "reservation", "confirm")):
        bid = uuid_m.group(0)
        b = _get_booking(f"/bookings/{bid}")
        return {"answer": _format_booking_reply(b)}

    # 3) UUID alone
    if uuid_m and len(_tok(text)) <= 5:
        bid = uuid_m.group(0)
        b = _get_booking(f"/bookings/{bid}")
        return {"answer": _format_booking_reply(b)}

    return None

# ── Models ─────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class HistoryEntry(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    collection: str = "example_business_docs"
    use_hyde: bool = True
    k_final: int = 6
    history: List[HistoryEntry] = Field(default_factory=list)  # avoid mutable default

# ── Helpers ───────────────────────────────────────────────────────────
def _normalize_history(h):
    out = []
    for m in h or []:
        if hasattr(m, "model_dump"):
            out.append(m.model_dump())
        elif isinstance(m, dict):
            out.append(m)
        else:
            try:
                out.append(dict(m))
            except Exception:
                pass
    return out

# ── Auth ─────────────────────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if not register_user(req.username, req.password, db):
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User registered successfully"}

@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    token = authenticate_user(req.username, req.password, db)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token}

# ── /ask (Blocking) ────────────────────────────────────────────────────
@router.post("/ask")
def ask(req: AskRequest, username=Depends(verify_token)):
    """
    Blocking Q&A with RRF + HYDE retrieval.
    Returns final answer + source list for UI citations.
    Enforces RAG-only answers for non-small-talk queries.
    """
    try:
        user_id = get_user_id(username)

        # 0) Booking chat (LLM-free) — short-circuit early
        handled = maybe_route_booking_chat(user_id, req.question) or maybe_handle_booking_intent(req.question)
        if handled:
            answer = handled["answer"]
            save_chat_history(user_id, req.question, answer)
            return {"question": req.question, "answer": answer, "sources": handled.get("sources", [])}

        # 1) Prefer provided history, else recent; normalize to dicts
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)

        # 2) Retrieve with RRF + HYDE
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # 3) Strict RAG gate for non-small-talk: require non-empty & relevant context
        if not _is_smalltalk_text(req.question):
            relevance = _ctx_relevance(req.question, rows)
            if (not rows) or (not ctx.strip()) or (relevance < 0.15):
                answer = "I don’t know."
                save_chat_history(user_id, req.question, answer)
                return {"question": req.question, "answer": answer, "sources": []}

        # 4) Convert history for LLM and pass fused context
        history_blocks = format_history_blocks(history_dicts)
        doc_context_str = ctx

        # 5) Ask the LLM grounded on the built context
        answer = ask_llm_hf(
            question=req.question,
            history_blocks=history_blocks,
            doc_context=doc_context_str,  # pass fused context string
            user_id=user_id,
        )

        # 6) Save chat
        save_chat_history(user_id, req.question, answer)

        # 7) Build sources for UI (rows = [(id, text, meta), ...])
        sources = [
            {
                "id": rid,
                "title": (meta.get("title") or meta.get("source_file") or (text[:80] + "…")),
                "url": meta.get("url", ""),
                "page": meta.get("page"),
            }
            for (rid, text, meta) in rows
        ]

        return {"question": req.question, "answer": answer, "sources": sources}

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ /ask failed:")
        raise HTTPException(status_code=500, detail=str(e))

# ── /ask/stream ───────────────────────────────────────────────────────
@router.post("/ask/stream")
async def stream(req: AskRequest, username=Depends(verify_token)):
    """
    Server-Sent Events stream of answer tokens.
    Sends an initial 'sources' event with citations before streaming tokens.
    Enforces RAG-only answers for non-small-talk queries.
    """
    try:
        user_id = get_user_id(username)

        # 0) Booking chat (LLM-free) — short-circuit early
        handled = maybe_route_booking_chat(user_id, req.question) or maybe_handle_booking_intent(req.question)
        if handled:
            answer = handled["answer"]

            def sse_booking():
                yield "retry: 2000\n\n"
                yield "event: sources\ndata: []\n\n"
                yield f"data: {json.dumps({'choices': [{'delta': {'content': answer}}]})}\n\n"
                yield "event: done\ndata: {}\n\n"
                try:
                    save_chat_history(user_id, req.question, answer)
                except Exception:
                    logging.exception("⚠️ Failed to save booking chat history.")

            return StreamingResponse(sse_booking(), media_type="text/event-stream")

        # 1) Prefer provided history, else recent; normalize to dicts
        history = req.history or get_recent_history(user_id)
        history_dicts = _normalize_history(history)

        # 2) Retrieve with RRF + HYDE
        ctx, rows = build_context_from_collection(
            collection=req.collection,
            query=req.question,
            use_real_hyde=req.use_hyde,
            k_final=req.k_final,
        )
        logging.info(f"[retrieval:/ask_stream] ctx_chars={len(ctx)} rows={len(rows)} q='{req.question[:60]}'")

        # 3) Non-small-talk strict gate: if no usable context, stream a short decline and end
        if not _is_smalltalk_text(req.question):
            relevance = _ctx_relevance(req.question, rows)
            if (not rows) or (not ctx.strip()) or (relevance < 0.15):
                def sse_generator_empty():
                    yield "retry: 2000\n\n"
                    yield f"event: sources\ndata: {json.dumps([])}\n\n"
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': 'I don’t know.'}}]})}\n\n"
                    yield "event: done\ndata: {}\n\n"
                    try:
                        save_chat_history(user_id, req.question, "I don’t know.")
                    except Exception:
                        logging.exception("⚠️ Failed to save chat history (empty).")
                return StreamingResponse(sse_generator_empty(), media_type="text/event-stream")

        # 4) Convert messages to LLM format
        history_blocks = format_history_blocks(history_dicts)
        doc_context = [ctx]  # ask_llm_hf_stream expects a list[str]

        # 5) Prepare sources for UI (rows = [(id, text, meta), ...])
        sources = [
            {
                "id": rid,
                "title": (meta.get("title") or meta.get("source_file") or (text[:80] + "…")),
                "url": meta.get("url", ""),
                "page": meta.get("page"),
            }
            for (rid, text, meta) in rows
        ]

        def sse_generator():
            full_answer = ""
            try:
                # (Optional) client retry hint
                yield "retry: 2000\n\n"

                # Send sources first
                yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

                # Stream tokens from the model
                for token in ask_llm_hf_stream(
                    question=req.question,
                    history_blocks=history_blocks,
                    doc_context=doc_context,
                    user_id=user_id,
                ):
                    if not token:
                        continue
                    full_answer += token
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': token}}]})}\n\n"

                yield "event: done\ndata: {}\n\n"

            except Exception as e:
                logging.exception("❌ Stream error:")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            finally:
                # Persist the complete answer
                try:
                    save_chat_history(user_id, req.question, full_answer)
                except Exception:
                    logging.exception("⚠️ Failed to save chat history at stream end.")

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ /ask/stream failed:")
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': str(e)})}\n\n"]),
            media_type="text/event-stream",
        )

# ── /history ──────────────────────────────────────────────────────────
@router.get("/history")
def history(username=Depends(verify_token)):
    user_id = get_user_id(username)
    return get_user_history(user_id)
