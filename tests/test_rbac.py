"""RBAC & auth-flow integration tests through the API."""
import warnings

import pytest

warnings.filterwarnings("ignore")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate storage per test run.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    from backend import config as cfg
    importlib.reload(cfg)
    from backend.services import auth, registry
    importlib.reload(auth)
    importlib.reload(registry)
    from backend import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def _hdr(tok):
    return {"Authorization": "Bearer " + tok}


def test_setup_register_and_rbac(client):
    # weak password rejected
    assert client.post("/api/auth/setup",
                       json={"username": "admin@x.com", "password": "weak"}).status_code == 400
    # first admin
    admin = client.post("/api/auth/setup",
                        json={"username": "admin@x.com", "password": "Str0ng!pass",
                              "full_name": "Admin"}).json()
    assert admin["user"]["role"] == "admin"
    # self-register -> user role
    user = client.post("/api/auth/register",
                       json={"username": "jane@x.com", "password": "Us3r!pass",
                             "full_name": "Jane"}).json()
    assert user["user"]["role"] == "user"
    # protected endpoint needs a token
    assert client.get("/api/documents").status_code == 401
    # regular user is forbidden from admin endpoints
    assert client.get("/api/admin/users", headers=_hdr(user["token"])).status_code == 403
    # admin can list users
    assert client.get("/api/admin/users", headers=_hdr(admin["token"])).status_code == 200


def test_last_admin_protection(client):
    admin = client.post("/api/auth/setup",
                        json={"username": "a@x.com", "password": "Str0ng!pass"}).json()
    h = _hdr(admin["token"])
    # cannot demote / delete the only admin
    assert client.patch("/api/admin/users/a@x.com", json={"role": "user"}, headers=h).status_code == 400
    assert client.delete("/api/admin/users/a@x.com", headers=h).status_code == 400
