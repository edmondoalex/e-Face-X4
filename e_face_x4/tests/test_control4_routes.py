import pytest

from asterisk_provisioner import control4_routes


def test_routes_are_isolated_and_persist(tmp_path, monkeypatch):
    root = tmp_path / "asterisk"
    (root / "custom").mkdir(parents=True)
    source = root / "custom" / "extensions.conf"
    source.write_text("[eface-test]\nexten => 8291,1,Goto(default,8291,1)\n[other]\n", encoding="utf-8")
    routes = control4_routes.Control4Routes(root)
    monkeypatch.setattr(control4_routes, "proxy_exists", lambda: True)
    monkeypatch.setattr(control4_routes, "extension_exists", lambda extension: False)
    monkeypatch.setattr(control4_routes, "route_matches", lambda extension, user: extension == "8293" and user == "000FFF8003BB")
    desired = [{"extension": "8293", "sip_user": "000FFF8003BB"}]
    assert routes.replace(desired, lambda: None) == desired
    assert routes.load() == desired
    assert "exten => 8291,1,Goto(default,8291,1)" in source.read_text(encoding="utf-8")
    assert "PJSIP/000FFF8003BB@control4-t3-ufficio-test" in routes.generated.read_text(encoding="utf-8")
    assert source.read_text(encoding="utf-8").count("#include /config/asterisk/eface/control4_routes.conf") == 1


def test_routes_roll_back_when_asterisk_does_not_confirm(tmp_path, monkeypatch):
    root = tmp_path / "asterisk"
    (root / "custom").mkdir(parents=True)
    (root / "custom" / "extensions.conf").write_text("[eface-test]\n", encoding="utf-8")
    routes = control4_routes.Control4Routes(root)
    monkeypatch.setattr(control4_routes, "proxy_exists", lambda: True)
    monkeypatch.setattr(control4_routes, "extension_exists", lambda extension: False)
    monkeypatch.setattr(control4_routes, "route_matches", lambda extension, user: False)
    with pytest.raises(RuntimeError):
        routes.replace([{"extension": "8293", "sip_user": "000FFF8003BB"}], lambda: None)
    assert routes.load() == []
    assert "PJSIP/000FFF8003BB" not in routes.generated.read_text(encoding="utf-8")


@pytest.mark.parametrize("routes", [
    [{"extension": "8291", "sip_user": "000FFF8003BB"}],
    [{"extension": "8293", "sip_user": "bad/user"}],
    [{"extension": "8293", "sip_user": "user"}, {"extension": "8293", "sip_user": "other"}],
])
def test_routes_reject_unmanaged_or_invalid_values(routes):
    with pytest.raises(ValueError):
        control4_routes.validate(routes)
