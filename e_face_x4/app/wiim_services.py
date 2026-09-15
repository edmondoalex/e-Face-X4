from __future__ import annotations


SERVICES = (
    {"id": "soundcloud", "name": "SoundCloud", "adapter": "official_api", "features": ["search", "tracks", "artists", "playlists", "likes"], "status": "configuration_required"},
    {"id": "spotify", "name": "Spotify", "adapter": "web_api", "features": ["search", "albums", "artists", "playlists", "library"], "status": "planned"},
    {"id": "amazon_music", "name": "Amazon Music", "adapter": "supported_path_required", "features": ["search", "albums", "artists", "playlists", "library"], "status": "research_required"},
    {"id": "bbc_radio", "name": "BBC Radio", "adapter": "radio_catalog", "features": ["stations", "shows", "search", "favorites"], "status": "planned"},
    {"id": "calm_radio", "name": "Calm Radio", "adapter": "official_api", "features": ["stations", "genres", "favorites"], "status": "research_required"},
    {"id": "deezer", "name": "Deezer", "adapter": "official_api", "features": ["search", "albums", "artists", "playlists", "favorites"], "status": "planned"},
    {"id": "hotmix", "name": "Hotmix", "adapter": "radio_catalog", "features": ["stations", "genres", "favorites"], "status": "planned"},
    {"id": "iheartradio", "name": "iHeartRadio", "adapter": "official_api", "features": ["search", "stations", "podcasts", "favorites"], "status": "research_required"},
    {"id": "network_stream", "name": "Apri flusso di rete", "adapter": "direct_stream", "features": ["stream_url", "m3u", "favorites"], "status": "next"},
    {"id": "youtube_music", "name": "YouTube Music", "adapter": "no_public_official_api", "features": ["cast", "external_app"], "status": "unsupported_catalog"},
    {"id": "tidal", "name": "TIDAL", "adapter": "official_api", "features": ["search", "albums", "artists", "playlists", "favorites"], "status": "planned"},
    {"id": "qobuz", "name": "Qobuz", "adapter": "official_api", "features": ["search", "albums", "artists", "playlists", "favorites"], "status": "planned"},
    {"id": "radio", "name": "Altre radio e podcast", "adapter": "direct_stream", "features": ["search", "stations", "podcasts", "favorites"], "status": "planned"},
    {"id": "home_music", "name": "Libreria locale", "adapter": "upnp_dlna", "features": ["browse", "search", "albums", "artists", "folders"], "status": "planned"},
    {"id": "other", "name": "Altri servizi WiiM", "adapter": "provider_specific", "features": ["inventory", "future_adapters"], "status": "inventory"},
)


def catalog() -> list[dict]:
    return [{**service, "features": list(service["features"])} for service in SERVICES]
