import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.recent_visibility import filter_recents, hidden_recents, hide_recent, load_hidden_recents, restore_recent, restore_recents


def test_recent_hide_and_restore(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_HIDDEN_RECENTS", str(tmp_path / "hidden.json"))
    items = [{"key": "a", "title": "A"}, {"key": "b", "title": "B"}]
    assert filter_recents(items) == (items, 0)
    assert hide_recent("a") == 1
    assert filter_recents(items) == ([items[1]], 1)
    assert "a" not in json.loads((tmp_path / "hidden.json").read_text(encoding="utf-8"))
    restore_recents()
    assert filter_recents(items) == (items, 0)


def test_recent_buttons_work_without_optional_user_accounts(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("EFACE_HIDDEN_RECENTS", str(tmp_path / "hidden.json"))
    client = TestClient(create_app())
    hidden = client.post("/api/control4/recently-played/hide", json={"key": "station-1"})
    assert hidden.status_code == 200
    assert hidden.json() == {"hidden_count": 1}
    restored = client.post("/api/control4/recently-played/restore", json={})
    assert restored.status_code == 200
    assert restored.json() == {"hidden_count": 0}


def test_recent_buttons_still_require_login_when_accounts_exist(monkeypatch, tmp_path):
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    (auth_dir / "users.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("EFACE_AUTH_DIR", str(auth_dir))
    monkeypatch.setenv("EFACE_HIDDEN_RECENTS", str(tmp_path / "hidden.json"))
    client = TestClient(create_app())
    assert client.post("/api/control4/recently-played/hide", json={"key": "station-1"}).status_code == 401
    assert client.post("/api/control4/recently-played/restore", json={}).status_code == 401


def test_recent_single_restore_and_persistence(monkeypatch, tmp_path):
    monkeypatch.setenv("EFACE_AUTH_DIR", str(tmp_path / "auth"))
    path = tmp_path / "hidden.json"
    monkeypatch.setenv("EFACE_HIDDEN_RECENTS", str(path))
    client = TestClient(create_app())
    for key in ("station-1", "station-2"):
        assert client.post("/api/control4/recently-played/hide", json={"key": key}).status_code == 200
    assert len(load_hidden_recents()) == 2
    assert hidden_recents([{"key": "station-1"}, {"key": "station-2"}]) == [{"key": "station-1"}, {"key": "station-2"}]
    result = client.post("/api/control4/recently-played/restore-one", json={"key": "station-1"})
    assert result.status_code == 200
    assert result.json() == {"hidden_count": 1}
    assert filter_recents([{"key": "station-1"}, {"key": "station-2"}]) == ([{"key": "station-1"}], 1)
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1
    assert len(load_hidden_recents()) == 1
