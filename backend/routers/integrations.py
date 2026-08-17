"""Integrations & Security status — surfaces connector authorization state to the UI.

Never returns a vague error: Microsoft connectors report their exact required permissions, whether
admin consent is needed, the ACTION REQUIRED block, and the legitimate export fallback.
"""
from fastapi import APIRouter

from connectors import registry as connector_registry

router = APIRouter(prefix="/api", tags=["integrations"])


@router.get("/integrations")
def integrations():
    return connector_registry.all_status()
