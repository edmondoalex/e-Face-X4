import uuid

from fastapi.testclient import TestClient

from app import personal_devices, provisioner_client
from app.main import create_app
from app.user_auth import create_account, create_admin
from asterisk_provisioner.managed_config import ManagedConfig


def test_device_inventory_persists_and_reserves_one_extension_per_browser(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    first = personal_devices.new_record(first_id, "mario", "Cellulare mario", {}, set())
    second = personal_devices.new_record(second_id, "mario", "PC mario", {first_id: first}, set())
    assert first["extension"] == "8302"
    assert second["extension"] == "8303"
    records = personal_devices.save({first_id: first, second_id: second})
    assert personal_devices.load() == records
    assert "password" not in str(personal_devices.public(records))
    personal_devices.revoke_id(first_id)
    assert first_id in personal_devices.revoked()
    config = ManagedConfig(tmp_path / "asterisk" / "eface")
    active = set()

    def reload():
        active.add(first["extension"])

    config.upsert(personal_devices.asterisk_username(first_id), first["extension"], first["password"], first["name"], reload, active.__contains__)
    assert "webrtc=yes" in config.pjsip.read_text(encoding="utf-8")
    assert "allow=!all,opus,alaw,ulaw,h264,vp8" in config.pjsip.read_text(encoding="utf-8")


def test_personal_device_api_provisions_and_revokes_individually(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "legacy.json"))
    remote = {}
    remote_groups = {"groups": []}

    async def fake_request(method, path, payload=None):
        if path == "/v1/intercom-groups" and method == "GET": return remote_groups
        if path == "/v1/intercom-groups" and method == "PUT": remote_groups["groups"] = payload["groups"]; return {"groups": payload["groups"], "provisioned": True}
        if method == "POST":
            remote[payload["username"]] = payload
            return {"extension": payload["extension"], "provisioned": True}
        if method == "DELETE":
            remote.pop(path.rsplit("/", 1)[-1], None)
            return {"removed": True}
        raise AssertionError((method, path))

    monkeypatch.setattr(provisioner_client, "request", fake_request)
    create_admin("password-admin-lunga")
    create_account("mario", "Mario Rossi", "password-mario-lunga")
    admin, person = TestClient(create_app()), TestClient(create_app())
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"}).status_code == 200
    device_id = str(uuid.uuid4())
    payload = {"device_id": device_id, "name": "Cellulare mario", "device_type": "phone", "video_capable": True}
    created = person.post("/api/intercom/sip/personal-device", json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["username"] == "8302"
    assert created.json()["video_capable"] is True
    assert created.json()["video_enabled"] is True
    assert person.post("/api/intercom/sip/personal-device", json=payload).json() == created.json()
    assert len(remote) == 1
    listed = admin.get("/api/admin/intercom/personal-devices")
    assert listed.json()["devices"][0]["extension"] == "8302"
    assert listed.json()["devices"][0]["device_type"] == "phone"
    assert "password" not in listed.text
    preferences = person.put(f"/api/intercom/personal-device/{device_id}/preferences", json={"name": "Poco Mario", "ringtone": "soft", "ring_volume": 55, "vibration": False, "silent": False})
    assert preferences.status_code == 200, preferences.text
    assert preferences.json()["ring_volume"] == 55
    video = person.put(f"/api/intercom/personal-device/{device_id}/preferences", json={"name":"Poco Mario","ringtone":"soft","ring_volume":55,"vibration":False,"silent":False,"video_enabled":True,"camera_facing":"environment"})
    assert video.json()["camera_facing"] == "environment"
    dnd = person.put(f"/api/intercom/personal-device/{device_id}/preferences", json={"name":"Poco Mario","ringtone":"soft","ring_volume":55,"vibration":False,"silent":False,"dnd":True})
    assert dnd.json()["dnd"] is True
    assert "8302" not in next(group for group in remote_groups["groups"] if group["extension"] == "8290")["members"]
    current_preferences = person.get(f"/api/intercom/personal-device/{device_id}/preferences").json()
    assert current_preferences["name"] == "Poco Mario"
    assert current_preferences["extension"] == "8302"
    assert admin.put(f"/api/admin/intercom/personal-devices/{device_id}", json={"name": "Telefono Mario"}).status_code == 200
    assert person.post("/api/intercom/sip/personal-device", json=payload).json()["name"] == "Telefono Mario"
    assert admin.delete(f"/api/admin/intercom/personal-devices/{device_id}").json() == {"removed": True}
    assert personal_devices.load() == {}
    assert remote == {}
    assert person.post("/api/intercom/sip/personal-device", json=payload).status_code == 403


def test_personal_device_push_subscription_and_call(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "legacy.json"))
    monkeypatch.setenv("EFACE_PUSH_DIR", str(tmp_path / "push"))
    async def fake_provision(method, path, payload=None):
        if path == "/v1/intercom-groups" and method == "GET": return {"groups": []}
        if path == "/v1/intercom-groups" and method == "PUT": return {"groups": payload["groups"], "provisioned": True}
        return {"extension": payload["extension"], "provisioned": True}
    monkeypatch.setattr(provisioner_client, "request", fake_provision)
    create_admin("password-admin-lunga")
    create_account("mario", "Mario", "password-mario-lunga", trusted_access=True)
    person = TestClient(create_app(), base_url="https://testserver")
    person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"})
    device_id = str(uuid.uuid4())
    created = person.post("/api/intercom/sip/personal-device", json={"device_id": device_id, "name": "Poco Mario", "device_type": "phone"})
    extension = created.json()["username"]
    subscription = {"endpoint": "https://push.example.test/id", "expirationTime": None, "keys": {"p256dh": "a" * 40, "auth": "b" * 20}}
    assert person.put(f"/api/intercom/push/subscription/{device_id}", json=subscription).json() == {"enabled": True}
    from app import push_notifications
    pushed = {}
    def fake_send(stored, payload):
        pushed.update(payload)
        return stored == subscription and payload["extension"] == extension
    monkeypatch.setattr(push_notifications, "send", fake_send)
    assert person.post(f"/api/intercom/push/call/{extension}").json() == {"sent": 1}
    assert person.post("/api/intercom/push/call/8290").json() == {"sent": 1}
    assert pushed["target"].startswith("intercom/wake/")
    person.post("/api/auth/logout")
    wake = person.get(f"/{pushed['target']}", follow_redirects=False, headers={"X-Forwarded-Proto": "https"})
    assert wake.status_code == 303
    assert wake.headers["location"].startswith("/intercom?push=1&from=Mario")
    assert "Max-Age=157680000" in wake.headers["set-cookie"]
    assert person.get("/intercom").status_code == 200
    assert person.get(f"/{pushed['target']}", follow_redirects=False).headers["location"] == "/login"
    assert person.delete(f"/api/intercom/push/subscription/{device_id}").json() == {"enabled": False}
    assert person.get("/service-worker.js").status_code == 200


def test_personal_device_rejects_invalid_id_and_admin(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    create_admin("password-admin-lunga")
    admin = TestClient(create_app())
    assert admin.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    assert admin.post("/api/intercom/sip/personal-device", json={"device_id": str(uuid.uuid4()), "name": "PC", "device_type": "desktop"}).status_code == 403


def test_personal_device_skips_unmanaged_asterisk_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    monkeypatch.setenv("EFACE_SIP_ACCOUNTS", str(tmp_path / "legacy.json"))

    async def fake_request(method, path, payload=None):
        if path == "/v1/intercom-groups" and method == "GET": return {"groups": []}
        if path == "/v1/intercom-groups" and method == "PUT": return {"groups": payload["groups"], "provisioned": True}
        if method == "DELETE": return {"removed": True}
        if payload["extension"] == "8302":
            raise RuntimeError("Interno non valido o già assegnato")
        return {"extension": payload["extension"], "provisioned": True}

    monkeypatch.setattr(provisioner_client, "request", fake_request)
    create_admin("password-admin-lunga")
    create_account("mario", "Mario Rossi", "password-mario-lunga")
    person = TestClient(create_app())
    person.post("/api/auth/login", json={"username": "mario", "password": "password-mario-lunga"})
    result = person.post("/api/intercom/sip/personal-device", json={"device_id": str(uuid.uuid4()), "name": "PC mario", "device_type": "desktop"})
    assert result.status_code == 200, result.text
    assert result.json()["username"] == "8303"
