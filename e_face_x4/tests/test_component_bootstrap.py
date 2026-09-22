import json

import app.component_bootstrap as bootstrap


def test_bootstrap_restarts_core_once_when_component_is_not_loaded(monkeypatch, tmp_path) -> None:
    manifest = tmp_path / "custom_components" / "eface_alexa" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    marker = tmp_path / "restart-marker"
    calls = []

    monkeypatch.setattr(bootstrap, "MANIFEST", manifest)
    monkeypatch.setattr(bootstrap, "MARKER", marker)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "redacted-test-token")
    monkeypatch.setattr(bootstrap, "_request", lambda path, _token, method="GET": calls.append((path, method)) or ((200, b'[{"domain":"light"}]') if path.endswith("services") else (200, b"{}")))

    bootstrap.main()
    bootstrap.main()

    assert calls.count(("/core/api/services/homeassistant/restart", "POST")) == 1
    assert marker.read_text(encoding="utf-8") == "1.1.0"


def test_bootstrap_does_not_restart_when_component_is_loaded(monkeypatch, tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(bootstrap, "MANIFEST", manifest)
    monkeypatch.setattr(bootstrap, "MARKER", tmp_path / "marker")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "redacted-test-token")
    monkeypatch.setattr(bootstrap, "_request", lambda path, _token, method="GET": calls.append((path, method)) or (200, b'[{"domain":"eface_alexa"}]'))

    bootstrap.main()

    assert calls == [("/core/api/services", "GET")]
