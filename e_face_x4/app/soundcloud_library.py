from __future__ import annotations
import json, os, re, time, shutil
from pathlib import Path
from typing import Any

def _path() -> Path:
    return Path(os.environ.get("EFACE_SOUNDCLOUD_LIBRARY", "/data/soundcloud_library.json"))

def load() -> dict[str, Any]:
    try: data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): data = {}
    playlists = data.get("playlists", []) if isinstance(data.get("playlists"), list) else []
    try: legacy_time = _path().stat().st_mtime
    except OSError: legacy_time = 0
    for index, playlist in enumerate(playlists):
        if isinstance(playlist, dict) and not playlist.get("updated_at"):
            playlist["updated_at"] = legacy_time - index / 1000
    return {"favorites": data.get("favorites", []) if isinstance(data.get("favorites"), list) else [], "recent": data.get("recent", []) if isinstance(data.get("recent"), list) else [], "playlists": playlists}

def _track(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not re.fullmatch(r"soundcloud:tracks:\d+", str(value.get("urn") or "")):
        raise ValueError("Brano SoundCloud non valido")
    clean = {key: str(value.get(key) or "")[:2048] for key in ("urn", "title", "artist", "artwork", "permalink_url")}
    clean.update({"type": "track", "duration": max(0, min(int(value.get("duration") or 0), 86400)), "playable": True})
    return clean

def _save(data: dict) -> None:
    path = _path(); path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(".tmp")
    if path.is_file():
        backup = path.with_suffix(".json.bak")
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"); os.chmod(temporary, 0o600); temporary.replace(path)

def remember(value: Any) -> dict:
    item = _track(value); data = load(); data["recent"] = [item] + [x for x in data["recent"] if x.get("urn") != item["urn"]][:39]; _save(data); return data

def toggle(value: Any) -> dict:
    item = _track(value); data = load(); existing = any(x.get("urn") == item["urn"] for x in data["favorites"])
    data["favorites"] = [x for x in data["favorites"] if x.get("urn") != item["urn"]]
    if not existing:
        item["saved_at"] = time.time()
        data["favorites"].insert(0, item)
    _save(data); return data

def remove_favorite(urn: str) -> dict:
    urn = str(urn or "").strip()
    if not re.fullmatch(r"soundcloud:tracks:\d+", urn):
        raise ValueError("Brano SoundCloud non valido")
    data = load()
    before = len(data["favorites"])
    data["favorites"] = [item for item in data["favorites"] if str(item.get("urn") or "") != urn]
    if len(data["favorites"]) == before:
        raise ValueError("Preferito SoundCloud non trovato")
    _save(data)
    return data

def save_to_playlist(name: str, value: Any, playlist_id: str = "") -> dict:
    item = _track(value); data = load(); name = str(name).strip()[:80]
    if playlist_id:
        playlist = next((x for x in data["playlists"] if x.get("id") == playlist_id), None)
        if not playlist:
            if not name or not re.fullmatch(r"[a-z0-9-]{1,60}", playlist_id):
                raise ValueError("Lista SoundCloud non trovata")
            playlist = {"id": playlist_id, "name": name, "tracks": []}
            data["playlists"].insert(0, playlist)
        data["playlists"] = [playlist] + [x for x in data["playlists"] if x is not playlist]
    else:
        if not name: raise ValueError("Inserisci il nome della nuova lista")
        playlist_id = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:50] or "lista"
        base, suffix = playlist_id, 2
        while any(x.get("id") == playlist_id for x in data["playlists"]): playlist_id, suffix = f"{base}-{suffix}", suffix + 1
        playlist = {"id": playlist_id, "name": name, "tracks": []}; data["playlists"].insert(0, playlist)
    playlist["tracks"] = [x for x in playlist.get("tracks", []) if x.get("urn") != item["urn"]] + [item]
    playlist["updated_at"] = time.time()
    _save(data); return data

def delete_playlist(playlist_id: str) -> dict:
    data = load(); before = len(data["playlists"]); data["playlists"] = [x for x in data["playlists"] if x.get("id") != playlist_id]
    if len(data["playlists"]) == before: raise ValueError("Lista SoundCloud non trovata")
    _save(data); return data

def playlist(playlist_id: str) -> dict:
    item = next((x for x in load()["playlists"] if x.get("id") == playlist_id), None)
    if not item: raise ValueError("Lista SoundCloud non trovata")
    return item

def retain_playlist_tracks(playlist_id: str, urns: list[str]) -> dict:
    data = load(); playlist = next((x for x in data["playlists"] if x.get("id") == playlist_id), None)
    if not playlist: raise ValueError("Lista SoundCloud non trovata")
    allowed = set(urns)
    playlist["tracks"] = [track for track in playlist.get("tracks", []) if str(track.get("urn") or "") in allowed]
    playlist["updated_at"] = time.time()
    _save(data)
    return playlist
