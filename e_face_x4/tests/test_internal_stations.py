import json

import pytest

from app import internal_stations


def test_internal_station_names_persist_and_default(monkeypatch, tmp_path):
    path = tmp_path / "internal_stations.json"
    monkeypatch.setenv("EFACE_INTERNAL_STATIONS", str(path))
    assert internal_stations.load() == {"8291": "Ufficio", "8292": "Tavolo"}
    expected = {"8291": "Studio", "8292": "Salotto"}
    assert internal_stations.save(expected) == expected
    assert internal_stations.load() == expected
    assert json.loads(path.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize("value", [
    {"8291": "Solo uno"},
    {"8291": "", "8292": "Tavolo"},
    {"8291": "Ufficio\naltro", "8292": "Tavolo"},
    {"8291": "Ufficio", "8292": 8292},
])
def test_internal_station_names_reject_invalid(monkeypatch, tmp_path, value):
    monkeypatch.setenv("EFACE_INTERNAL_STATIONS", str(tmp_path / "internal_stations.json"))
    with pytest.raises(ValueError):
        internal_stations.save(value)
