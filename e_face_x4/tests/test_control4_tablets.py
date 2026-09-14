import json

import pytest
from fastapi.testclient import TestClient

from app import control4_tablets
from app.main import create_app


def test_inventory_persists_without_modifying_existing_beta_tablets(monkeypatch, tmp_path):
    path = tmp_path / "tablets.json"
    monkeypatch.setenv("EFACE_CONTROL4_TABLETS", str(path))
    assert control4_tablets.load() == []
    value = [{"extension": "8293", "name": "Cucina", "sip_user": "000FFF8003BB"}]
    assert control4_tablets.save(value) == value
    assert control4_tablets.load() == value
    assert json.loads(path.read_text(encoding="utf-8")) == value


@pytest.mark.parametrize("value", [
    [{"extension": "8291", "name": "Beta", "sip_user": "000FFF8003BB"}],
    [{"extension": "8293", "name": "Cucina\naltro", "sip_user": "000FFF8003BB"}],
    [{"extension": "8293", "name": "Cucina", "sip_user": "bad/user"}],
    [{"extension": "8293", "name": "A", "sip_user": "same"}, {"extension": "8294", "name": "B", "sip_user": "Same"}],
])
def test_inventory_rejects_invalid_records(monkeypatch, tmp_path, value):
    monkeypatch.setenv("EFACE_CONTROL4_TABLETS", str(tmp_path / "tablets.json"))
    with pytest.raises(ValueError):
        control4_tablets.save(value)


def test_tablets_api_requires_admin_and_never_claims_provisioned(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_CONTROL4_TABLETS", str(tmp_path / "tablets.json"))
    client = TestClient(create_app())
    assert client.put("/api/admin/intercom/control4-tablets", json={"tablets": []}).status_code in (401, 403)


def test_tablets_api_confirms_route_before_persisting(monkeypatch, tmp_path):
    from app import provisioner_client
    from app.user_auth import create_admin

    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_CONTROL4_TABLETS", str(tmp_path / "tablets.json"))
    routes = []

    async def fake_request(method, path, payload=None):
        assert path == "/v1/control4-tablets"
        if method == "PUT":
            routes[:] = payload["tablets"]
        return {"tablets": list(routes), "provisioned": True}

    monkeypatch.setattr(provisioner_client, "request", fake_request)
    monkeypatch.setattr(provisioner_client, "public", lambda: {"configured": True})
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    tablet = {"extension": "8293", "name": "Cucina", "sip_user": "000FFF8003BB"}
    response = client.put("/api/admin/intercom/control4-tablets", json={"tablets": [tablet]})
    assert response.status_code == 200, response.text
    assert response.json()["tablets"] == [{**tablet, "status": "route_present"}]
    assert control4_tablets.load() == [tablet]
    assert client.get("/api/intercom/internal-stations").json()["tablets"] == [
        {"extension": "8293", "name": "Cucina", "ready": True}
    ]
