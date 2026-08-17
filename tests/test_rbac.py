"""RBAC, multi-tenant, and auth-flow integration tests through the API."""
import importlib
import warnings

import pytest

warnings.filterwarnings("ignore")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALLOW_REGISTRATION", "false")
    from backend import config as cfg
    importlib.reload(cfg)
    from backend.services import auth, properties, registry
    importlib.reload(auth)
    importlib.reload(registry)
    importlib.reload(properties)
    from backend import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c, auth


def _h(tok):
    return {"Authorization": "Bearer " + tok}


def test_setup_requires_key(client):
    c, _ = client
    assert c.post("/api/auth/setup",
                  json={"username": "a@x.com", "password": "Str0ng!pass"}).status_code == 403


def test_first_account_is_superadmin_and_default_property(client):
    c, auth = client
    su = c.post("/api/auth/setup",
                json={"username": "me@x.com", "password": "Str0ng!pass",
                      "setup_key": auth.setup_key(), "full_name": "Me"}).json()
    assert su["user"]["role"] == "superadmin"
    props = c.get("/api/properties", headers=_h(su["token"])).json()
    assert props["can_manage"] and len(props["properties"]) >= 1


def test_rbac_and_tenant_isolation(client):
    c, auth = client
    su = c.post("/api/auth/setup",
                json={"username": "me@x.com", "password": "Str0ng!pass",
                      "setup_key": auth.setup_key()}).json()
    H = _h(su["token"])
    default_id = c.get("/api/properties", headers=H).json()["properties"][0]["id"]
    site_b = c.post("/api/properties", json={"name": "Site B"}, headers=H).json()

    # superadmin creates users in specific properties
    assert c.post("/api/admin/users", headers=H,
                  json={"username": "u@x.com", "password": "Us3r!pass", "role": "user",
                        "property_id": default_id}).status_code == 200
    assert c.post("/api/admin/users", headers=H,
                  json={"username": "b-admin@x.com", "password": "Adm1n!pass", "role": "admin",
                        "property_id": site_b["id"]}).status_code == 200

    # regular user: forbidden from admin + property management
    utok = c.post("/api/auth/login", json={"username": "u@x.com", "password": "Us3r!pass"}).json()["token"]
    assert c.get("/api/admin/users", headers=_h(utok)).status_code == 403
    assert c.post("/api/properties", json={"name": "x"}, headers=_h(utok)).status_code == 403
    up = c.get("/api/properties", headers=_h(utok)).json()
    assert up["can_manage"] is False and len(up["properties"]) == 1

    # property admin (Site B) sees only Site B users
    batok = c.post("/api/auth/login",
                   json={"username": "b-admin@x.com", "password": "Adm1n!pass"}).json()["token"]
    blist = c.get("/api/admin/users", headers=_h(batok)).json()
    assert {u["username"] for u in blist} == {"b-admin@x.com"}

    # documents are isolated per property (empty each here)
    assert c.get("/api/documents", headers=H).json() == []
    assert c.get("/api/documents", headers={**H, "X-Property-Id": str(site_b["id"])}).json() == []

    # registration disabled; last superadmin protected
    assert c.post("/api/auth/register",
                  json={"username": "z@x.com", "password": "Zzz1!pass"}).status_code == 403
    assert c.delete("/api/admin/users/me@x.com", headers=H).status_code == 400


def test_disabled_user_blocked_immediately(client):
    c, auth = client
    su = c.post("/api/auth/setup",
                json={"username": "me@x.com", "password": "Str0ng!pass",
                      "setup_key": auth.setup_key()}).json()
    H = _h(su["token"])
    pid = c.get("/api/properties", headers=H).json()["properties"][0]["id"]
    c.post("/api/admin/users", headers=H,
           json={"username": "u@x.com", "password": "Us3r!pass", "role": "user", "property_id": pid})
    utok = c.post("/api/auth/login", json={"username": "u@x.com", "password": "Us3r!pass"}).json()["token"]
    assert c.get("/api/documents", headers=_h(utok)).status_code == 200
    # disable -> the existing token stops working immediately (role/state read from DB)
    c.patch("/api/admin/users/u@x.com", json={"disabled": True}, headers=H)
    assert c.get("/api/documents", headers=_h(utok)).status_code == 401
