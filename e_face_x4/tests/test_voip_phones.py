import pytest
from fastapi.testclient import TestClient

from app import provisioner_client, voip_phones
from app.main import create_app
from app.user_auth import create_admin
from asterisk_provisioner.managed_config import ManagedConfig
from asterisk_provisioner.voip_routes import VoipRoutes


def test_voip_inventory_and_render_are_persistent_and_profiled(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_VOIP_PHONES", str(tmp_path / "phones.json"))
    extension, record = voip_phones.new_record("Studio", "voip_video", {})
    assert extension == "8350"
    assert voip_phones.save({extension: record}) == {extension: record}
    assert voip_phones.load() == {extension: record}
    assert "password" not in str(voip_phones.public(voip_phones.load()))
    config = ManagedConfig(tmp_path / "asterisk" / "eface")
    existing = set()

    def reload():
        existing.add(extension)

    config.upsert(f"voip_{extension}", extension, record["password"], record["name"], reload, existing.__contains__, record["profile"])
    generated = config.pjsip.read_text(encoding="utf-8")
    assert "webrtc=no" in generated
    assert "context=eface-test" in generated
    assert "allow=!all,alaw,ulaw,h264,vp8" in generated
    assert f"[{extension}]" in generated


def test_voip_route_include_preserves_existing_dialplan(tmp_path):
    root = tmp_path / "asterisk"
    (root / "custom").mkdir(parents=True)
    source = root / "custom" / "extensions.conf"
    source.write_text("[eface-test]\nexten => 8291,1,Goto(default,8291,1)\n[other]\n", encoding="utf-8")
    routes = VoipRoutes(root)
    routes.ensure(lambda: None)
    routes.ensure(lambda: None)
    assert source.read_text(encoding="utf-8").count("#include /config/asterisk/eface/voip_routes.conf") == 1
    assert "8291" in source.read_text(encoding="utf-8")
    assert "_83[5-9]X" in routes.generated.read_text(encoding="utf-8")
    assert "_830[2-9]" in routes.generated.read_text(encoding="utf-8")
    assert "_83[1-4]X" in routes.generated.read_text(encoding="utf-8")
    assert "exten => 8301,1,Dial(PJSIP/8301,40)" in routes.generated.read_text(encoding="utf-8")


def test_voip_route_content_update_reloads_existing_include(tmp_path):
    root = tmp_path / "asterisk"
    (root / "custom").mkdir(parents=True)
    (root / "custom" / "extensions.conf").write_text("[eface-test]\n#include /config/asterisk/eface/voip_routes.conf\n", encoding="utf-8")
    routes = VoipRoutes(root)
    routes.directory.mkdir(parents=True)
    routes.generated.write_text("; old version\n", encoding="utf-8")
    calls = []
    routes.ensure(lambda: calls.append("reload"))
    assert calls == ["reload"]
    assert "_830[2-9]" in routes.generated.read_text(encoding="utf-8")


def test_voip_api_provisions_before_exposing_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_VOIP_PHONES", str(tmp_path / "phones.json"))
    remote = {}

    async def fake_request(method, path, payload=None):
        if method == "GET":
            return {"phones": [{"extension": item["extension"], "name": item["name"], "profile": item["profile"]} for item in remote.values()]}
        if method == "POST":
            remote[payload["extension"]] = payload
            return {"extension": payload["extension"], "provisioned": True}
        if method == "DELETE":
            remote.pop(path.rsplit("_", 1)[-1], None)
            return {"removed": True}
        raise AssertionError(method)

    monkeypatch.setattr(provisioner_client, "request", fake_request)
    monkeypatch.setattr(provisioner_client, "public", lambda: {"configured": True})
    create_admin("password-admin-lunga")
    client = TestClient(create_app())
    assert client.post("/api/admin/intercom/voip-phones", json={"name": "Studio", "profile": "voip_audio"}).status_code in (401, 403)
    assert client.post("/api/auth/login", json={"username": "admin", "password": "password-admin-lunga"}).status_code == 200
    created = client.post("/api/admin/intercom/voip-phones", json={"name": "Studio", "profile": "voip_audio"})
    assert created.status_code == 200, created.text
    assert created.json()["extension"] == "8350"
    assert created.json()["password"] == voip_phones.load()["8350"]["password"]
    listed = client.get("/api/admin/intercom/voip-phones")
    assert listed.json()["phones"] == [{"extension": "8350", "name": "Studio", "profile": "voip_audio", "endpoint_present": True}]
    assert "password" not in listed.text
    assert client.put("/api/admin/intercom/voip-phones/8350", json={"name": "Studio nuovo", "profile": "voip_video"}).status_code == 200
    assert voip_phones.load()["8350"]["profile"] == "voip_video"
    assert client.delete("/api/admin/intercom/voip-phones/8350").json() == {"removed": True}
    assert voip_phones.load() == {}


@pytest.mark.parametrize("profile", ["invalid", "browser", "voip_video\n[other]"])
def test_voip_rejects_invalid_profiles(profile):
    with pytest.raises(ValueError):
        voip_phones.new_record("Studio", profile, {})
