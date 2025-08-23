from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations.servicenow_client import IncidentCreate, create_incident

# Use the canonical variable name `router` (cleaner to import elsewhere)
router = APIRouter(prefix="/integrations/servicenow", tags=["servicenow"])

class IncidentRequest(BaseModel):
    short_description: str
    description: str | None = None
    urgency: str | None = None   # "high"/"medium"/"low" or "1/2/3"
    impact: str | None = None
    category: str | None = None
    subcategory: str | None = None
    caller_id: str | None = None
    assignment_group: str | None = None
    assigned_to: str | None = None
    location: str | None = None

@router.get("/_ping")
def ping():
    return {"ok": True}

@router.post("/incident")
def sn_create_incident(body: IncidentRequest):
    try:
        result = create_incident(IncidentCreate(**body.dict()))
        return {
            "ok": True,
            "number": result.get("number"),
            "sys_id": result.get("sys_id"),
            "link": f"/nav_to.do?uri=incident.do?sys_id={result.get('sys_id')}" if result.get("sys_id") else None,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ServiceNow error: {e}")
