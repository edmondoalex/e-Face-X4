import json

from app.recent_visibility import filter_recents, hide_recent, restore_recents


def test_recent_hide_and_restore(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_HIDDEN_RECENTS", str(tmp_path / "hidden.json"))
    items = [{"key": "a", "title": "A"}, {"key": "b", "title": "B"}]
    assert filter_recents(items) == (items, 0)
    assert hide_recent("a") == 1
    assert filter_recents(items) == ([items[1]], 1)
    assert "a" not in json.loads((tmp_path / "hidden.json").read_text(encoding="utf-8"))
    restore_recents()
    assert filter_recents(items) == (items, 0)
