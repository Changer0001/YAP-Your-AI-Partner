import time
import requests
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os

SN_INSTANCE = os.getenv("SN_INSTANCE", "").rstrip("/")
SN_AUTH_MODE = os.getenv("SN_AUTH_MODE", "oauth")  # "oauth" or "basic"
SN_CLIENT_ID = os.getenv("SN_CLIENT_ID")
SN_CLIENT_SECRET = os.getenv("SN_CLIENT_SECRET")
SN_USERNAME = os.getenv("SN_USERNAME")
SN_PASSWORD = os.getenv("SN_PASSWORD")

_token_cache = {"access_token": None, "exp": 0}

class IncidentCreate(BaseModel):
    short_description: str
    description: Optional[str] = None
    urgency: Optional[str] = None        # 1=High,2=Medium,3=Low (SN values)
    impact: Optional[str] = None         # 1,2,3
    category: Optional[str] = None
    subcategory: Optional[str] = None
    caller_id: Optional[str] = None
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    location: Optional[str] = None

def _oauth_token() -> str:
    now = int(time.time())
    if _token_cache["access_token"] and now < _token_cache["exp"] - 30:
        return _token_cache["access_token"]

    url = f"{SN_INSTANCE}/oauth_token.do"
    data = {
        "grant_type": "client_credentials",
        "client_id": SN_CLIENT_ID,
        "client_secret": SN_CLIENT_SECRET,
    }
    resp = requests.post(url, data=data, timeout=20)
    resp.raise_for_status()
    tok = resp.json()
    _token_cache["access_token"] = tok["access_token"]
    _token_cache["exp"] = now + tok.get("expires_in", 1800)
    return _token_cache["access_token"]

def _auth_headers() -> Dict[str, str]:
    if SN_AUTH_MODE == "basic":
        from requests.auth import HTTPBasicAuth
        # Basic auth passed separately via 'auth' param
        return {"Content-Type": "application/json", "Accept": "application/json"}
    else:
        return {
            "Authorization": f"Bearer {_oauth_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

def create_incident(payload: IncidentCreate) -> Dict[str, Any]:
    url = f"{SN_INSTANCE}/api/now/table/incident"
    headers = _auth_headers()
    auth = None
    if SN_AUTH_MODE == "basic":
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(SN_USERNAME, SN_PASSWORD)

    data = {k: v for k, v in payload.dict().items() if v is not None}
    # Map friendly values to SN numerics if provided as words
    if data.get("urgency") in ("high", "1"): data["urgency"] = "1"
    elif data.get("urgency") in ("medium", "2"): data["urgency"] = "2"
    elif data.get("urgency") in ("low", "3"): data["urgency"] = "3"

    if data.get("impact") in ("high", "1"): data["impact"] = "1"
    elif data.get("impact") in ("medium", "2"): data["impact"] = "2"
    elif data.get("impact") in ("low", "3"): data["impact"] = "3"

    resp = requests.post(url, headers=headers, auth=auth, json=data, timeout=20)
    resp.raise_for_status()
    out = resp.json()
    if "result" not in out:
        raise RuntimeError(f"Unexpected ServiceNow response: {out}")
    return out["result"]
