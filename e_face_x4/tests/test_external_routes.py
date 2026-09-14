from __future__ import annotations

import pytest

from asterisk_provisioner.external_routes import ExternalRoutes


def test_external_routes_are_persistent_and_isolated(tmp_path, monkeypatch) -> None:
    custom = tmp_path / "custom"
    custom.mkdir()
    source = custom / "extensions.conf"
    original = "[default]\nexten => 8290,1,Dial(PJSIP/8301)\n[eface-test]\nexten => 8290,1,Goto(default,8290,1)\n[other]\nexten => 123,1,Hangup()\n"
    source.write_text(original, encoding="utf-8")
    routes = ExternalRoutes(tmp_path)
    reloads = []
    routes.ensure(lambda: reloads.append("reload"))
    assert len(reloads) == 1
    monkeypatch.setattr("asterisk_provisioner.external_routes.route_matches", lambda extension, host: extension == "8202" and host == "192.168.2.31")
    assert routes.backup.read_text(encoding="utf-8") == original
    assert "#include /config/asterisk/eface/external_routes.conf\n[other]" in source.read_text(encoding="utf-8")
    routes.ensure(lambda: reloads.append("reload"))
    assert len(reloads) == 1
    routes.replace([{"extension": "8202", "host": "192.168.2.31"}],
                   lambda: reloads.append("reload"), lambda extension: len(reloads) > 1 and extension == "8202")
    assert routes.load() == [{"extension": "8202", "host": "192.168.2.31"}]
    assert "Dial(PJSIP/doorbird-p2p-test/sip:192.168.2.31:5060,40)" in routes.generated.read_text(encoding="utf-8")


def test_external_routes_reject_non_private_host(tmp_path) -> None:
    routes = ExternalRoutes(tmp_path)
    with pytest.raises(ValueError, match="privato"):
        routes.replace([{"extension": "8202", "host": "8.8.8.8"}], lambda: None, lambda extension: False)
