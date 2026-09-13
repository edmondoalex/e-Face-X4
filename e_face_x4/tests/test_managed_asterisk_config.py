from __future__ import annotations

import json

import pytest

from asterisk_provisioner.managed_config import ManagedConfig, render


def test_persistent_phone_survives_reconcile(tmp_path) -> None:
    config = ManagedConfig(tmp_path / "asterisk" / "eface")
    existing = set()
    reloads = []

    def reload_pjsip() -> None:
        reloads.append(True)
        existing.add("8302")

    config.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex", reload_pjsip, existing.__contains__)
    assert len(reloads) == 1
    assert config.state.is_file()
    assert config.pjsip.is_file()
    assert config.state_backup.is_file()
    assert config.pjsip_backup.is_file()
    assert not config.pending.exists()
    assert "context=eface-test" in config.pjsip.read_text(encoding="utf-8")
    assert "8301" not in config.pjsip.read_text(encoding="utf-8")
    config.pjsip.unlink()
    ManagedConfig(config.directory).reconcile_file()
    assert "password=A_secure_personal_secret_123456789" in config.pjsip.read_text(encoding="utf-8")
    assert config.load()["ekonex"]["extension"] == "8302"


def test_rollback_if_asterisk_does_not_load_endpoint(tmp_path) -> None:
    config = ManagedConfig(tmp_path)
    with pytest.raises(RuntimeError, match="non vede"):
        config.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex", lambda: None, lambda _: False)
    assert json.loads(config.state.read_text(encoding="utf-8")) == {}
    assert "[8302]" not in config.pjsip.read_text(encoding="utf-8")
    assert not config.pending.exists()


def test_startup_recovers_interrupted_transaction(tmp_path) -> None:
    config = ManagedConfig(tmp_path)
    config.reconcile_file()
    config.state_backup.write_text("{}", encoding="utf-8")
    config.pjsip_backup.write_text(render({}), encoding="utf-8")
    config.state.write_text('{"ekonex": {"extension": "8302"}}', encoding="utf-8")
    config.pjsip.write_text("broken", encoding="utf-8")
    config.pending.write_text("pending", encoding="utf-8")
    config.reconcile_file()
    assert config.load() == {}
    assert config.pjsip.read_text(encoding="utf-8") == render({})
    assert not config.pending.exists()


def test_rejects_static_collision_and_config_injection(tmp_path) -> None:
    config = ManagedConfig(tmp_path)
    with pytest.raises(ValueError, match="fuori da e-Face"):
        config.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex", lambda: None, lambda _: True)
    assert not config.state.exists()
    with pytest.raises(ValueError, match="Password"):
        render({"ekonex": {"extension": "8302", "password": "secret\n[8301]", "name": "Ekonex"}})
    with pytest.raises(ValueError, match="duplicato"):
        render({
            "ekonex": {"extension": "8302", "password": "A_secure_personal_secret_123456789", "name": "Ekonex"},
            "mario": {"extension": "8302", "password": "Another_secure_personal_secret_123", "name": "Mario"},
        })


def test_revocation_is_persistent_and_rolls_back_if_endpoint_remains(tmp_path) -> None:
    config = ManagedConfig(tmp_path)
    active = set()

    def enable() -> None:
        active.add("8302")

    config.upsert("ekonex", "8302", "A_secure_personal_secret_123456789", "Ekonex", enable, active.__contains__)
    with pytest.raises(RuntimeError, match="ancora"):
        config.revoke("ekonex", lambda: None, active.__contains__)
    assert "ekonex" in config.load()
    assert not config.pending.exists()

    def disable() -> None:
        active.discard("8302")

    assert config.revoke("ekonex", disable, active.__contains__) is True
    assert config.load() == {}
    assert "[8302]" not in config.pjsip.read_text(encoding="utf-8")
    assert config.revoke("ekonex", disable, active.__contains__) is False
