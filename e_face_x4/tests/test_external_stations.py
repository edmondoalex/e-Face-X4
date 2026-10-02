from __future__ import annotations

import json

import pytest

from app import external_stations


def test_external_stations_default_and_persistent_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    monkeypatch.setenv("EFACE_EXTERNAL_STATIONS", str(tmp_path / "external.json"))
    default = external_stations.load()
    assert default[0]["id"] == "ingresso"
    assert default[0]["name"] == "Doorbird Cancello"
    assert default[0]["sip_extension"] == "8201"
    extra = {"id": "esterno-2", "name": "Cancello", "host": "192.168.2.31", "http_port": 80,
             "sip_extension": "8202", "ready": False, "username": "operator", "password": "secret"}
    external_stations.save([default[0], extra])
    assert (tmp_path / "external.json").is_file()
    assert "secret" not in str(external_stations.public())
    assert "secret" not in str(external_stations.admin_public())
    assert external_stations.get("esterno-2")["password"] == "secret"
    extra["password"] = ""
    external_stations.save([default[0], extra])
    assert external_stations.get("esterno-2")["password"] == "secret"


@pytest.mark.parametrize("legacy_name", ["Ingresso · DoorBird", "Cancello"])
def test_primary_doorbird_legacy_name_is_migrated_for_display(monkeypatch, tmp_path, legacy_name: str) -> None:
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    path = tmp_path / "external.json"
    monkeypatch.setenv("EFACE_EXTERNAL_STATIONS", str(path))
    station = external_stations._default()[0]
    station["name"] = legacy_name
    path.write_text(json.dumps([station]), encoding="utf-8")

    assert external_stations.load()[0]["name"] == "Doorbird Cancello"


def test_external_stations_reject_duplicate_and_public_ips(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_INTERCOM_SETTINGS", str(tmp_path / "intercom.json"))
    monkeypatch.setenv("EFACE_EXTERNAL_STATIONS", str(tmp_path / "external.json"))
    default = external_stations.load()[0]
    extra = {**default, "id": "esterno-2", "name": "Cancello", "host": "192.168.2.31"}
    with pytest.raises(ValueError, match="duplicato"):
        external_stations.save([default, extra])
    extra["sip_extension"] = "8202"
    extra["host"] = "8.8.8.8"
    with pytest.raises(ValueError, match="privato"):
        external_stations.save([default, extra])
