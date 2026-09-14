from __future__ import annotations

import pytest

from app import provisioner_client


def test_provisioner_pairing_is_persistent_and_hides_token(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EFACE_PROVISIONER_SETTINGS", str(tmp_path / "pairing.json"))
    token = "A" * 48
    value = provisioner_client.save({"host": "192.168.3.24", "port": 9443,
                                     "token": token, "fingerprint": "b" * 64})
    assert value["configured"] is True
    assert token not in str(value)
    assert provisioner_client.load()["token"] == token
    provisioner_client.save({"host": "192.168.3.24", "port": 9443,
                             "token": "", "fingerprint": "b" * 64})
    assert provisioner_client.load()["token"] == token
    with pytest.raises(ValueError, match="privato"):
        provisioner_client.save({"host": "8.8.8.8", "port": 9443,
                                 "token": token, "fingerprint": "b" * 64})
