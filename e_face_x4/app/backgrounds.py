from __future__ import annotations

import base64, binascii, hashlib, json, os, re, secrets
from pathlib import Path
from urllib.parse import urlsplit

PRESETS = {"teal", "midnight", "graphite", "ocean", "warm"}
CARD_THEMES = {"graphite", "petrol", "midnight", "slate", "warm"}
SECURITY_ORDER = ["scenarios", "areas", "zones", "locks", "cameras"]
SHORTCUT_CATEGORIES = ["lights", "switches", "covers", "climate", "security", "media", "sensors", "other"]
DEVICE_ORGANIZATION_CATEGORIES = ["lights", "extra", "covers", "comfort", "security", "scenarios", "intercom", "media"]
NAVIGATION_ITEMS = ["watch", "listen", "intercom", "lights", "extra", "scenarios", "covers", "comfort", "heating", "energy", "security", "shopping", "alexa-agenda"]
LEGACY_HOME_WIDGETS = ["overview", "weather", "camera_event", "doorbell", "motion", "states", "rooms", "live"]
NEW_HOME_WIDGETS = ["room_pulse", "lights_now", "routine_pulse", "shopping_list", "agenda"]
HOME_WIDGETS = [*LEGACY_HOME_WIDGETS, *NEW_HOME_WIDGETS]
DEFAULT_HOME_WIDGETS = [
    {"id": "overview", "visible": True, "size": "wide", "height": "short"},
    {"id": "states", "visible": True, "size": "wide", "height": "short"},
    {"id": "live", "visible": True, "size": "wide", "height": "short"},
    {"id": "weather", "visible": True, "size": "quarter", "height": "standard"},
    {"id": "camera_event", "visible": True, "size": "quarter", "height": "uniform"},
    {"id": "doorbell", "visible": True, "size": "quarter", "height": "uniform"},
    {"id": "motion", "visible": True, "size": "quarter", "height": "uniform"},
    {"id": "rooms", "visible": True, "size": "wide", "height": "short"},
    {"id": "lights_now", "visible": True, "size": "quarter", "height": "short"},
    {"id": "routine_pulse", "visible": True, "size": "quarter", "height": "short"},
    {"id": "shopping_list", "visible": True, "size": "quarter", "height": "short"},
    {"id": "agenda", "visible": True, "size": "quarter", "height": "short"},
    {"id": "room_pulse", "visible": False, "size": "wide", "height": "standard"},
]
MIME_SUFFIX = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}

def _directory() -> Path: return Path(os.environ.get("EFACE_BACKGROUNDS", "/data/backgrounds"))
def _key(room: str | None) -> str: return "global" if not room else "room-" + hashlib.sha256(room.encode()).hexdigest()[:20]

def _config() -> dict:
    try: raw = json.loads((_directory() / "selection.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): raw = {}
    return raw if isinstance(raw, dict) else {}

def load_background(room: str | None = None) -> dict[str, str]:
    raw = _config(); selected = raw.get("rooms", {}).get(room) if room and isinstance(raw.get("rooms"), dict) else raw.get("global")
    if not isinstance(selected, dict): selected = {"mode": "inherit"} if room else {"mode": "preset", "preset": "teal"}
    mode, preset = str(selected.get("mode") or "inherit"), str(selected.get("preset") or "teal")
    if mode == "custom" and not load_background_image(room): mode = "inherit" if room else "preset"
    return {"mode": mode if mode in {"preset", "custom", "inherit"} else "inherit", "preset": preset if preset in PRESETS else "teal"}

def load_backgrounds() -> dict:
    raw = _config(); rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}
    return {"global": load_background(), "rooms": {room: load_background(room) for room in rooms}}

def load_card_theme() -> str:
    value = str(_config().get("card_theme") or "graphite")
    return value if value in CARD_THEMES else "graphite"

def save_card_theme(theme: str) -> None:
    if theme not in CARD_THEMES: raise ValueError("Colore card non valido")
    raw = _config(); raw["card_theme"] = theme; _write(raw)

def load_room_order() -> list[str]:
    value = _config().get("room_order")
    return [name for name in value if isinstance(name, str) and name.strip()][:200] if isinstance(value, list) else []

def save_room_order(names: list[str]) -> None:
    if not isinstance(names, list) or len(names) > 200 or any(not isinstance(name, str) or not name.strip() or len(name) > 100 for name in names):
        raise ValueError("Ordine ambienti non valido")
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Ambienti duplicati")
    raw = _config(); raw["room_order"] = names; _write(raw)

def load_security_order() -> list[str]:
    value = _config().get("security_order")
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        if len(value) == len(SECURITY_ORDER) and set(value) == set(SECURITY_ORDER): return value
        previous = [item for item in SECURITY_ORDER if item != "cameras"]
        if len(value) == len(previous) and set(value) == set(previous): return [*value, "cameras"]
    return SECURITY_ORDER.copy()

def save_security_order(order: list[str]) -> None:
    if not isinstance(order, list) or len(order) != len(SECURITY_ORDER) or not all(isinstance(item, str) for item in order) or set(order) != set(SECURITY_ORDER):
        raise ValueError("Ordine sicurezza non valido")
    raw = _config(); raw["security_order"] = order; _write(raw)

def load_security_cameras() -> list[dict[str, str]]:
    value = _config().get("security_cameras")
    if not isinstance(value, list): return []
    result = []
    for item in value[:100]:
        if not isinstance(item, dict): continue
        camera_id, name, url = str(item.get("id") or "").strip(), str(item.get("name") or "").strip(), str(item.get("url") or "").strip()
        mode = "video" if item.get("mode") == "video" else "snapshot"
        preview_url, video_url = str(item.get("preview_url") or "").strip(), str(item.get("video_url") or "").strip()
        if camera_id and name and url:
            camera = {"id": camera_id[:80], "name": name[:100], "url": url[:2000], "mode": mode}
            if preview_url: camera["preview_url"] = preview_url[:2000]
            if video_url: camera["video_url"] = video_url[:2000]
            result.append(camera)
    return result

def save_security_cameras(cameras: list[dict[str, str]]) -> None:
    if not isinstance(cameras, list) or len(cameras) > 100: raise ValueError("Elenco videocamere non valido")
    clean, ids = [], set()
    for item in cameras:
        if not isinstance(item, dict): raise ValueError("Videocamera non valida")
        camera_id, name, url = str(item.get("id") or "").strip(), str(item.get("name") or "").strip(), str(item.get("url") or "").strip()
        mode = "video" if item.get("mode") == "video" else "snapshot"
        preview_url, video_url = str(item.get("preview_url") or "").strip(), str(item.get("video_url") or "").strip()
        if not name or len(name) > 100: raise ValueError("Nome videocamera non valido")
        if not url or len(url) > 2000: raise ValueError("Link o entità videocamera non valido")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", camera_id) or camera_id in ids:
            camera_id = secrets.token_hex(16)
        parsed = urlsplit(url)
        is_entity = bool(re.fullmatch(r"camera\.[a-z0-9_]+", url))
        if not (is_entity or (parsed.scheme in {"http", "https"} and parsed.netloc) or (not parsed.scheme and url.startswith("/") and not url.startswith("//"))):
            raise ValueError("Inserisci un'entità camera.* oppure un link HTTP, HTTPS o locale")
        camera = {"id": camera_id, "name": name, "url": url, "mode": mode}
        if preview_url: camera["preview_url"] = preview_url
        if video_url: camera["video_url"] = video_url
        ids.add(camera_id); clean.append(camera)
    raw = _config(); raw["security_cameras"] = clean; _write(raw)

def load_shortcuts() -> list[dict[str, object]]:
    value = _config().get("shortcuts")
    if not isinstance(value, list): return []
    result = []
    for group in value[:len(SHORTCUT_CATEGORIES)]:
        if not isinstance(group, dict) or group.get("category") not in SHORTCUT_CATEGORIES: continue
        devices = group.get("devices")
        if not isinstance(devices, list): continue
        clean = [item for item in devices if isinstance(item, str) and 0 < len(item) <= 200]
        result.append({"category": group["category"], "devices": list(dict.fromkeys(clean))[:250]})
    return result

def save_shortcuts(groups: list[dict[str, object]]) -> None:
    if not isinstance(groups, list) or len(groups) > len(SHORTCUT_CATEGORIES): raise ValueError("Scorciatoie non valide")
    categories, device_ids, clean = set(), set(), []
    for group in groups:
        if not isinstance(group, dict) or group.get("category") not in SHORTCUT_CATEGORIES or group["category"] in categories: raise ValueError("Categoria scorciatoie non valida")
        devices = group.get("devices")
        if not isinstance(devices, list) or len(devices) > 250: raise ValueError("Dispositivi scorciatoia non validi")
        normalized = []
        for item in devices:
            if not isinstance(item, str) or not item or len(item) > 200 or item in device_ids: raise ValueError("Dispositivo scorciatoia non valido")
            device_ids.add(item); normalized.append(item)
        categories.add(group["category"]); clean.append({"category": group["category"], "devices": normalized})
    raw = _config(); raw["shortcuts"] = clean; _write(raw)

def load_device_organization() -> dict[str, dict[str, object]]:
    value = _config().get("device_organization")
    if not isinstance(value, dict): return {}
    result = {}
    for device_id, item in list(value.items())[:2000]:
        if not isinstance(device_id, str) or not device_id or len(device_id) > 200 or not isinstance(item, dict): continue
        categories = item.get("categories")
        clean_categories = [category for category in categories if category in DEVICE_ORGANIZATION_CATEGORIES] if isinstance(categories, list) else []
        orders = item.get("orders") if isinstance(item.get("orders"), dict) else {}
        clean_orders = {key: max(0, int(value)) for key, value in orders.items() if key in ["devices", *DEVICE_ORGANIZATION_CATEGORIES] and isinstance(value, int)}
        result[device_id] = {"visible": item.get("visible") is not False, "categories": list(dict.fromkeys(clean_categories)), "orders": clean_orders}
    return result

def save_device_organization(value: dict[str, dict[str, object]]) -> None:
    if not isinstance(value, dict) or len(value) > 2000: raise ValueError("Organizzazione dispositivi non valida")
    clean = {}
    for device_id, item in value.items():
        if not isinstance(device_id, str) or not device_id or len(device_id) > 200 or not isinstance(item, dict): raise ValueError("Dispositivo organizzato non valido")
        categories = item.get("categories")
        if not isinstance(categories, list) or any(category not in DEVICE_ORGANIZATION_CATEGORIES for category in categories): raise ValueError("Categoria dispositivo non valida")
        orders = item.get("orders") if isinstance(item.get("orders"), dict) else {}
        if any(key not in ["devices", *DEVICE_ORGANIZATION_CATEGORIES] or not isinstance(order, int) or order < 0 for key, order in orders.items()): raise ValueError("Ordine dispositivo non valido")
        clean[device_id] = {"visible": item.get("visible") is not False, "categories": list(dict.fromkeys(categories)), "orders": orders}
    raw = _config(); raw["device_organization"] = clean; _write(raw)

def load_navigation_items() -> list[dict[str, object]]:
    value = _config().get("navigation_items")
    entries = value if isinstance(value, list) else []
    clean = [{"id": item["id"], "visible": item.get("visible") is not False} for item in entries
             if isinstance(item, dict) and item.get("id") in NAVIGATION_ITEMS]
    seen = {item["id"] for item in clean}
    return list(dict((item["id"], item) for item in clean).values()) + [{"id": key, "visible": True} for key in NAVIGATION_ITEMS if key not in seen]

def save_navigation_items(value: list[dict[str, object]]) -> None:
    if not isinstance(value, list) or len(value) != len(NAVIGATION_ITEMS) or any(
        not isinstance(item, dict) or item.get("id") not in NAVIGATION_ITEMS or not isinstance(item.get("visible"), bool) for item in value
    ) or len({item["id"] for item in value}) != len(NAVIGATION_ITEMS):
        raise ValueError("Navigazione non valida")
    raw = _config(); raw["navigation_items"] = [{"id": item["id"], "visible": item["visible"]} for item in value]; _write(raw)

def load_home_widgets(owner: str | None = None) -> list[dict[str, object]]:
    raw = _config(); users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}
    scoped = users.get(owner) if owner and isinstance(users.get(owner), dict) else {}
    account_owner = owner.split(":device:", 1)[0] if owner and ":device:" in owner else None
    account = users.get(account_owner) if account_owner and isinstance(users.get(account_owner), dict) else {}
    value = scoped.get("home_widgets") if owner else raw.get("home_widgets")
    if owner and not isinstance(value, list): value = account.get("home_widgets")
    if owner and not isinstance(value, list): value = raw.get("home_widgets")
    if not isinstance(value, list):
        return [dict(item) for item in DEFAULT_HOME_WIDGETS]
    clean, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or item.get("id") not in HOME_WIDGETS or item["id"] in seen: continue
        seen.add(item["id"]); size = item.get("size")
        height = item.get("height")
        clean.append({"id": item["id"], "visible": item.get("visible") is not False, "size": size if size in {"quarter", "compact", "standard", "large", "wide"} else "standard", "height": height if height in {"uniform", "short", "standard", "tall"} else "standard"})
    for widget_id in HOME_WIDGETS:
        if widget_id not in seen: clean.append({"id": widget_id, "visible": widget_id not in NEW_HOME_WIDGETS, "size": "wide" if widget_id == "room_pulse" else "standard", "height": "standard"})
    return clean

def save_home_widgets(items: list[dict[str, object]], owner: str | None = None) -> None:
    if not isinstance(items, list) or len(items) not in {len(LEGACY_HOME_WIDGETS), len(HOME_WIDGETS)}: raise ValueError("Configurazione Home non valida")
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    if len(ids) != len(items) or any(not isinstance(widget_id, str) for widget_id in ids): raise ValueError("Widget Home non validi")
    if (frozenset(ids) not in {frozenset(LEGACY_HOME_WIDGETS), frozenset(HOME_WIDGETS)}
            or len(ids) != len(set(ids))): raise ValueError("Widget Home non validi")
    clean = []
    for item in items:
        if not isinstance(item.get("visible"), bool) or item.get("size") not in {"quarter", "compact", "standard", "large", "wide"} or item.get("height", "standard") not in {"uniform", "short", "standard", "tall"}: raise ValueError("Proprietà widget non valide")
        clean.append({"id": item["id"], "visible": item["visible"], "size": item["size"], "height": item.get("height", "standard")})
    for widget_id in NEW_HOME_WIDGETS:
        if widget_id not in ids:
            clean.append({"id": widget_id, "visible": False, "size": "wide" if widget_id == "room_pulse" else "standard", "height": "standard"})
    raw = _config()
    if owner:
        users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}; scoped = users.get(owner) if isinstance(users.get(owner), dict) else {}; scoped["home_widgets"] = clean; users[owner] = scoped; raw["user_appearance"] = users
    else: raw["home_widgets"] = clean
    _write(raw)

def load_home_camera_entity(owner: str | None = None) -> str:
    raw = _config()
    shared = str(raw.get("home_camera_entity") or "").strip()
    if shared:
        value = shared
    else:
        # Automatic migration: a previously scoped value becomes the shared
        # installation setting returned to every panel.
        users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}
        value = next((str(item.get("home_camera_entity") or "").strip() for item in users.values() if isinstance(item, dict) and str(item.get("home_camera_entity") or "").strip()), "camera.nvr_32ch_ext_ultimo_evento")
    return value if re.fullmatch(r"camera\.[a-z0-9_]+", value) else "camera.nvr_32ch_ext_ultimo_evento"

def save_home_camera_entity(entity_id: str, owner: str | None = None) -> None:
    if not isinstance(entity_id, str) or not re.fullmatch(r"camera\.[a-z0-9_]+", entity_id): raise ValueError("Entità telecamera non valida")
    raw = _config(); raw["home_camera_entity"] = entity_id
    users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}
    for scoped in users.values():
        if isinstance(scoped, dict): scoped.pop("home_camera_entity", None)
    _write(raw)

def load_home_weather_location(owner: str | None = None) -> str:
    raw = _config()
    shared = str(raw.get("home_weather_location") or "").strip()
    if shared: return shared
    # Automatic migration: the first location previously saved on a browser
    # becomes the installation-wide default for every other panel.
    users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}
    return next((str(item.get("home_weather_location") or "").strip() for item in users.values() if isinstance(item, dict) and str(item.get("home_weather_location") or "").strip()), "")

def save_home_weather_location(location: str, owner: str | None = None) -> None:
    if not isinstance(location, str) or not 2 <= len(location.strip()) <= 100: raise ValueError("Località meteo non valida")
    value = location.strip(); raw = _config(); raw["home_weather_location"] = value
    users = raw.get("user_appearance") if isinstance(raw.get("user_appearance"), dict) else {}
    for scoped in users.values():
        if isinstance(scoped, dict): scoped.pop("home_weather_location", None)
    _write(raw)

def load_home_todo_entity() -> str:
    value = str(_config().get("home_todo_entity") or "").strip().lower()
    return value if re.fullmatch(r"todo\.[a-z0-9_]+", value) else ""

def save_home_todo_entity(entity_id: str) -> None:
    if not isinstance(entity_id, str) or not re.fullmatch(r"todo\.[a-z0-9_]+", entity_id.strip().lower()):
        raise ValueError("Lista e-Control non valida")
    raw = _config(); raw["home_todo_entity"] = entity_id.strip().lower(); _write(raw)

def load_home_agenda_source() -> str:
    value = str(_config().get("home_agenda_source") or "alexa").strip().lower()
    return value if value in {"alexa", "econtrol"} or re.fullmatch(r"calendar\.[a-z0-9_]+", value) else "alexa"

def save_home_agenda_source(value: str) -> None:
    value = str(value or "").strip().lower()
    if value not in {"alexa", "econtrol"} and not re.fullmatch(r"calendar\.[a-z0-9_]+", value): raise ValueError("Sorgente agenda non valida")
    raw = _config(); raw["home_agenda_source"] = value; _write(raw)

def load_card_glow() -> bool:
    return _config().get("card_glow", True) is not False

def save_card_glow(enabled: bool) -> None:
    if not isinstance(enabled, bool): raise ValueError("Valore illuminazione non valido")
    raw = _config(); raw["card_glow"] = enabled; _write(raw)

def save_preset(preset: str, room: str | None = None) -> None:
    if preset not in PRESETS: raise ValueError("Sfondo predefinito non valido")
    _save_selection({"mode": "preset", "preset": preset}, room)

def save_inherit(room: str) -> None:
    if not room: raise ValueError("Stanza non valida")
    raw = _config(); rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}; rooms.pop(room, None); raw["rooms"] = rooms; _write(raw)

def save_background_image(mime: str, encoded: str, room: str | None = None) -> None:
    if mime not in MIME_SUFFIX: raise ValueError("Formato foto non valido")
    try: content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError("Dati foto non validi") from exc
    valid = (mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    if not valid or not 16 <= len(content) <= 4_000_000: raise ValueError("Foto non valida o superiore a 4 MB")
    directory = _directory(); directory.mkdir(parents=True, exist_ok=True); key = _key(room)
    for suffix in MIME_SUFFIX.values():
        try: (directory / f"{key}{suffix}").unlink()
        except FileNotFoundError: pass
    target = directory / f"{key}{MIME_SUFFIX[mime]}"; temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content); os.chmod(temporary, 0o600); temporary.replace(target); _save_selection({"mode": "custom", "preset": "teal"}, room)

def load_background_image(room: str | None = None) -> tuple[str, bytes] | None:
    key = _key(room)
    for mime, suffix in MIME_SUFFIX.items():
        try: content = (_directory() / f"{key}{suffix}").read_bytes()
        except OSError: continue
        if 16 <= len(content) <= 4_000_000: return mime, content
    return None

def _save_selection(value: dict, room: str | None) -> None:
    raw = _config()
    if room:
        rooms = raw.get("rooms") if isinstance(raw.get("rooms"), dict) else {}; rooms[room] = value; raw["rooms"] = rooms
    else: raw["global"] = value
    _write(raw)

def _write(value: dict) -> None:
    directory = _directory(); directory.mkdir(parents=True, exist_ok=True); target = directory / "selection.json"; temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8"); os.chmod(temporary, 0o600); temporary.replace(target)
