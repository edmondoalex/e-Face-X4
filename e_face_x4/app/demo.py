from __future__ import annotations


def dashboard() -> dict:
    return {
        "home": {"name": "Casa", "weather": "Sereno", "temperature": 23},
        "rooms": [
            {"id": "living", "name": "Soggiorno", "devices": 8, "accent": "amber"},
            {"id": "kitchen", "name": "Cucina", "devices": 6, "accent": "blue"},
            {"id": "office", "name": "Ufficio", "devices": 5, "accent": "violet"},
            {"id": "outside", "name": "Esterno", "devices": 7, "accent": "green"},
        ],
        "widgets": [
            {"id": "lights", "kind": "metric", "title": "Luci", "value": "7", "detail": "accese su 24", "icon": "light"},
            {"id": "climate", "kind": "metric", "title": "Clima", "value": "22°", "detail": "Comfort", "icon": "climate"},
            {"id": "security", "kind": "metric", "title": "Sicurezza", "value": "OK", "detail": "Tutto protetto", "icon": "shield"},
            {"id": "energy", "kind": "metric", "title": "Energia", "value": "2.4 kW", "detail": "Consumo casa", "icon": "energy"},
        ],
        "media": {
            "playing": True,
            "title": "Cosmic Trouble",
            "artist": "MaxRiven",
            "source": "Spotify Connect",
            "room": "Ufficio Alex",
            "volume": 46,
        },
    }

