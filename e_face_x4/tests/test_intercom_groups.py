from pathlib import Path

import pytest

from app import control4_tablets, intercom_groups, personal_devices
from asterisk_provisioner.intercom_groups import IntercomGroups, render


def test_group_validation_and_dialplan() -> None:
    groups = [{"extension": "8290", "name": "Tutti", "members": ["8303", "8291", "8303"]}]
    assert intercom_groups.validate(groups)[0]["members"] == ["8291", "8303"]
    dialplan = render(groups)
    assert "Local/8291@eface-test/n&Local/8303@eface-test/n" in dialplan
    with pytest.raises(ValueError): intercom_groups.validate([{"extension":"8291","name":"No","members":[]}])


def test_asterisk_group_replace_is_persistent(monkeypatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "extensions.conf").write_text("[default]\nexten => 8290,1,Dial(PJSIP/old,40)\n[eface-test]\nexten => 8290,1,Goto(default,8290,1)\n[other]\n", encoding="utf-8")
    manager = IntercomGroups(tmp_path)
    reloads = []
    manager.ensure(lambda: reloads.append(True))
    groups = [{"extension":"8280","name":"Famiglia","members":["8291","8302"]}]
    assert manager.replace(groups, lambda: reloads.append(True)) == groups
    assert manager.load() == groups
    assert "#include /config/asterisk/eface/intercom_groups.conf" in (custom / "extensions.conf").read_text(encoding="utf-8")
    assert "Goto(eface-groups,8290,1)" in (custom / "extensions.conf").read_text(encoding="utf-8")
    assert "Local/8302@eface-test/n" in manager.generated.read_text(encoding="utf-8")


def test_default_group_excludes_personal_dnd_but_keeps_control4(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EFACE_PERSONAL_DEVICES", str(tmp_path / "devices.json"))
    monkeypatch.setenv("EFACE_CONTROL4_TABLETS", str(tmp_path / "tablets.json"))
    monkeypatch.setenv("EFACE_VOIP_PHONES", str(tmp_path / "voip.json"))
    first_id, second_id = "00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002"
    first = personal_devices.new_record(first_id, "mario", "Cellulare", {}, set(), "phone")
    second = personal_devices.new_record(second_id, "mario", "Tablet", {first_id:first}, set(), "tablet")
    second["dnd"] = True
    records = personal_devices.save({first_id:first, second_id:second})
    control4_tablets.save([{"extension":"8293","name":"Cucina","sip_user":"cucina"}])
    group = intercom_groups.with_default([], records)[0]
    assert group["members"] == ["8291", "8292", "8293", "8302"]
