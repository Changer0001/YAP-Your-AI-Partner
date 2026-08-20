"""Properties (tenants). Super-admin manages them; everyone else sees only their own."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import auth, properties, registry, vectorstore

router = APIRouter(prefix="/api/properties", tags=["properties"])


class PropertyBody(BaseModel):
    name: str


@router.get("")
def list_props(user: dict = Depends(auth.require_auth)):
    if user["role"] == "superadmin":
        return {"properties": properties.list_properties(), "can_manage": True}
    ids = user.get("property_ids") or ([user["property_id"]] if user.get("property_id") else [])
    props = [p for p in (properties.get_property(i) for i in ids) if p]
    return {"properties": props, "can_manage": False}


@router.post("")
def create_prop(body: PropertyBody, user: dict = Depends(auth.require_superadmin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    return properties.create_property(name)


@router.patch("/{pid}")
def rename_prop(pid: int, body: PropertyBody, user: dict = Depends(auth.require_superadmin)):
    if not properties.get_property(pid):
        raise HTTPException(404, "Property not found")
    properties.rename_property(pid, body.name.strip())
    return properties.get_property(pid)


@router.delete("/{pid}")
def delete_prop(pid: int, user: dict = Depends(auth.require_superadmin)):
    prop = properties.get_property(pid)
    if not prop:
        raise HTTPException(404, "Property not found")
    if properties.count() <= 1:
        raise HTTPException(400, "Cannot delete the only property")
    if auth.list_users(pid):
        raise HTTPException(400, "Reassign or remove this property's users first")
    # Delete its documents + isolated vector collection.
    for doc in registry.list_documents(pid):
        registry.delete_document(doc["id"])
    vectorstore.drop_collection(prop["collection"])
    properties.delete_property(pid)
    return {"deleted": pid}
