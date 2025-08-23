import os, hmac, hashlib, base64, time, re, json
from typing import Dict
from fastapi import APIRouter, Request, HTTPException

from app.retriever.rrf_hyde import build_context_from_collection
from app.llm.llm_interface import ask_llm_hf, format_history_blocks
from app.integrations.servicenow_client import IncidentCreate, create_incident

router = APIRouter(prefix="/integrations/teams", tags=["teams-outgoing"])

# Set this to the **token** shown by Teams when you create the outgoing webhook
TEAMS_WEBHOOK_SECRET = os.getenv("TEAMS_WEBHOOK_SECRET", "")

# tiny in-memory “pending ticket” store per (conversation+user)
PENDING: Dict[str, Dict] = {}

def _verify_signature(raw: bytes, auth_header: str | None) -> bool:
    """
    Teams computes: HMAC = base64( HMAC_SHA256( body, base64decode(secret) ) )
    Header: Authorization: HMAC <HMAC>
    """
    if not TEAMS_WEBHOOK_SECRET:
        # allow unsigned during dev if you didn't paste the secret yet
        return True
    if not auth_header or not auth_header.startswith("HMAC "):
        return False
    received = auth_header.split(" ", 1)[1]
    key = base64.b64decode(TEAMS_WEBHOOK_SECRET)
    digest = hmac.new(key, raw, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(received, expected)

def _clean_text(t: str) -> str:
    # remove <at>YAP</at> mention markup and collapse spaces
    t = re.sub(r"<at>.*?</at>", "", t or "", flags=re.I)
    return re.sub(r"\s+", " ", t).strip()

def _parse_ticket_fields(user_text: str) -> dict:
    """
    Optional direct 'open a ticket' parser, e.g.:
    'open a ticket: printer down. priority high. impact low. details: tray jam'
    """
    t = user_text.strip()
    get = lambda rx: (re.search(rx, t, re.I) or [None, None])[1]
    short = get(r"open\s+a\s+ticket:\s*(.+?)(?:\.|$)") or t[:120]
    desc  = get(r"details?:\s*(.+)$")
    urg   = (get(r"priority\s+(high|medium|low|1|2|3)") or "").lower() or None
    imp   = (get(r"impact\s+(high|medium|low|1|2|3)") or "").lower() or None
    return {"short_description": short, "description": desc, "urgency": urg, "impact": imp}

@router.post("/webhook")
async def teams_outgoing_webhook(request: Request):
    raw = await request.body()
    if not _verify_signature(raw, request.headers.get("Authorization")):
        raise HTTPException(status_code=401, detail="Signature verification failed")

    body = await request.json()
    text = _clean_text(body.get("text", ""))
    user = (body.get("from", {}) or {}).get("name", "user")
    conv = (body.get("conversation", {}) or {}).get("id", "conv")
    key  = f"{conv}:{user}".lower()

    # --- 'ticket' confirmation command ---
    if text.lower() in {"ticket", "open ticket", "yes", "y"}:
        pending = PENDING.get(key)
        if not pending:
            return {"text": "No pending question to escalate. Ask me something first."}
        short = pending["q"][:160]
        details = (
            f"Teams user: {user}\n\n"
            f"Question: {pending['q']}\n"
            f"Assistant: {pending['a']}\n"
            f"(requested via Teams outgoing webhook)"
        )
        try:
            res = create_incident(IncidentCreate(
                short_description=short,
                description=details,
                urgency="2",  # medium
                impact="3",   # low
            ))
            number, sys_id = res.get("number"), res.get("sys_id")
            base = os.getenv("SN_INSTANCE", "").rstrip("/")
            link = f"{base}/nav_to.do?uri=incident.do?sys_id={sys_id}" if (base and sys_id) else ""
            PENDING.pop(key, None)
            return {"text": f"✅ Created ServiceNow incident **{number}**  {link}"}
        except Exception as e:
            return {"text": f"❌ Failed to create incident: {e}"}

    # --- direct 'open a ticket: ...' fallback (optional) ---
    if text.lower().startswith("open a ticket"):
        fields = _parse_ticket_fields(text)
        try:
            res = create_incident(IncidentCreate(**fields))
            number, sys_id = res.get("number"), res.get("sys_id")
            base = os.getenv("SN_INSTANCE", "").rstrip("/")
            link = f"{base}/nav_to.do?uri=incident.do?sys_id={sys_id}" if (base and sys_id) else ""
            return {"text": f"✅ Incident **{number}** created. {link}"}
        except Exception as e:
            return {"text": f"❌ Failed to create incident: {e}"}

    # --- Normal Q&A with YAP ---
    try:
        ctx, rows = build_context_from_collection(
            collection="example_business_docs",
            query=text,
            use_real_hyde=True,
            k_final=6,
        )
        answer = ask_llm_hf(
            question=text,
            history_blocks=format_history_blocks([]),
            doc_context=ctx,
            user_id=user,
        )
    except Exception as e:
        return {"text": f"❌ Error: {e}"}

    msg = answer or ""
    if msg.strip().lower().startswith("i don’t know"):
        PENDING[key] = {"q": text, "a": msg, "ts": time.time()}
        msg += "\n\nReply **ticket** to open a ServiceNow incident."
    return {"text": msg}
