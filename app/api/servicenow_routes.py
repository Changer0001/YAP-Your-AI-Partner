from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.integrations.servicenow_client import IncidentCreate, create_incident
from fastapi import APIRouter

router_sn = APIRouter(prefix="/integrations/servicenow", tags=["servicenow"])

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

@router_sn.post("/incident")
def sn_create_incident(body: IncidentRequest):
    try:
        result = create_incident(IncidentCreate(**body.dict()))
        return {
            "number": result.get("number"),
            "sys_id": result.get("sys_id"),
            "link": result.get("links", [{}])[0].get("url", None) if result.get("links") else None,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ServiceNow error: {e}")
