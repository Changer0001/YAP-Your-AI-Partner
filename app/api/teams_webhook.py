import hmac, hashlib, base64, os, json, re
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import requests
import os
from app.integrations.servicenow_client import IncidentCreate, create_incident


router_teams = APIRouter(prefix="/integrations/teams", tags=["teams"])
TEAMS_SECRET = os.getenv("TEAMS_WEBHOOK_SECRET", "")

# --- Pydantic model for outgoing webhook payload (subset) ---
class TeamsWebhook(BaseModel):
    text: str
    from_name: str | None = None  # Teams may include "from" metadata depending on config

def _verify_signature(raw_body: bytes, auth_header: str) -> bool:
    if not TEAMS_SECRET or not auth_header:
        return False
    mac = hmac.new(TEAMS_SECRET.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(auth_header.replace("HMAC ", ""), expected)

def _parse_ticket_fields(user_text: str) -> dict:
    """
    Minimal parser. For better results, call YAP LLM to extract fields.
    Patterns supported:
      "open a ticket: <short_description>. priority <high|medium|low>. impact <high|medium|low>. details: <description>"
    """
    t = user_text.strip()
    short_desc = None
    desc = None
    urgency = None
    impact = None

    # crude splits
    m = re.search(r"open\s+a\s+ticket:\s*(.+?)(?:\.|$)", t, re.I)
    if m: short_desc = m.group(1).strip()

    m = re.search(r"details?:\s*(.+)$", t, re.I)
    if m: desc = m.group(1).strip()

    m = re.search(r"priority\s+(high|medium|low|1|2|3)", t, re.I)
    if m: urgency = m.group(1).lower()

    m = re.search(r"impact\s+(high|medium|low|1|2|3)", t, re.I)
    if m: impact = m.group(1).lower()

    return {
        "short_description": short_desc or t[:120],
        "description": desc,
        "urgency": urgency,
        "impact": impact,
    }

@router_teams.post("/webhook")
async def teams_webhook(request: Request):
    raw = await request.body()
    auth_header = request.headers.get("Authorization", "")

    # Verify HMAC from Teams
    if not _verify_signature(raw, auth_header):
        raise HTTPException(status_code=401, detail="Signature verification failed")

    payload = TeamsWebhook(**json.loads(raw))

    fields = _parse_ticket_fields(payload.text)

    # Fallback: ask YAP to extract structured fields (optional)
    # Example:
    # fields = await call_yap_to_parse(payload.text)  # implement if you want richer NLU

    # Call our ServiceNow incident endpoint
    try:
        result = create_incident(IncidentCreate(**fields))
        number = result.get("number")
        sys_id = result.get("sys_id")
        sn_instance = os.getenv("SN_INSTANCE", "")
        link = f"{sn_instance}/nav_to.do?uri=incident.do?sys_id={sys_id}"
        text = f"✅ Incident **{number}** created.\n{link}"
    except Exception as e:
        text = f"❌ Failed to create incident: {e}"

    # Outgoing webhook expects `{ "text": "..." }`
    return {"text": text}
