from __future__ import annotations

import base64
import re
import time
from typing import Any

import httpx


class SoundCloudClient:
    _tokens: dict[str, tuple[str, float]] = {}

    def __init__(self, client_id: str, client_secret: str, *, transport: httpx.AsyncBaseTransport | None = None):
        if not client_id or not client_secret:
            raise ValueError("Credenziali SoundCloud non configurate")
        self.client_id, self.client_secret, self.transport = client_id, client_secret, transport
        self._token = ""; self._expires = 0.0

    @classmethod
    def clear_token(cls, client_id: str) -> None:
        cls._tokens.pop(str(client_id), None)

    async def token(self) -> str:
        cached = self._tokens.get(self.client_id)
        if cached and cached[1] > time.monotonic() + 60:
            return cached[0]
        if self._token and self._expires > time.monotonic() + 60:
            return self._token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with httpx.AsyncClient(transport=self.transport, timeout=10) as client:
            response = await client.post("https://secure.soundcloud.com/oauth/token", headers={"Authorization": f"Basic {basic}", "Accept": "application/json"}, data={"grant_type": "client_credentials"})
            response.raise_for_status(); payload = response.json()
        self._token = str(payload.get("access_token") or "")
        if not self._token:
            raise RuntimeError("Token SoundCloud mancante")
        self._expires = time.monotonic() + int(payload.get("expires_in") or 3600)
        self._tokens[self.client_id] = (self._token, self._expires)
        return self._token

    async def search_tracks(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        query = str(query).strip()
        if not 2 <= len(query) <= 120:
            raise ValueError("Ricerca SoundCloud non valida")
        async with httpx.AsyncClient(transport=self.transport, timeout=12) as client:
            response = await client.get("https://api.soundcloud.com/tracks", params={"q": query, "access": "playable", "limit": max(1, min(int(limit), 50)), "linked_partitioning": "true"}, headers={"Authorization": f"OAuth {await self.token()}", "Accept": "application/json"})
            response.raise_for_status(); payload = response.json()
        collection = payload.get("collection", []) if isinstance(payload, dict) else payload
        return [self._track(item) for item in collection if isinstance(item, dict)]

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(transport=self.transport, timeout=12) as client:
            response = await client.get(f"https://api.soundcloud.com/{path.lstrip('/')}", params=params, headers={"Authorization": f"OAuth {await self.token()}", "Accept": "application/json"})
            response.raise_for_status()
            return response.json()

    async def search(self, query: str, kind: str = "tracks", limit: int = 24) -> list[dict[str, Any]]:
        query = str(query).strip()
        if not 2 <= len(query) <= 120 or kind not in {"tracks", "playlists", "users"}:
            raise ValueError("Ricerca SoundCloud non valida")
        payload = await self._get(kind, params={"q": query, "limit": max(1, min(int(limit), 50)), "linked_partitioning": "true", **({"access": "playable"} if kind == "tracks" else {})})
        collection = payload.get("collection", []) if isinstance(payload, dict) else payload
        normalizer = {"tracks": self._track, "playlists": self._playlist, "users": self._user}[kind]
        return [normalizer(item) for item in collection if isinstance(item, dict)]

    async def playlist_tracks(self, urn: str) -> list[dict[str, Any]]:
        urn = self._urn(urn, "playlists")
        payload = await self._get(f"playlists/{urn}/tracks", params={"access": "playable", "limit": 50, "linked_partitioning": "true"})
        collection = payload.get("collection", []) if isinstance(payload, dict) else payload
        return [self._track(item) for item in collection if isinstance(item, dict)]

    async def user_tracks(self, urn: str) -> list[dict[str, Any]]:
        urn = self._urn(urn, "users")
        payload = await self._get(f"users/{urn}/tracks", params={"access": "playable", "limit": 50, "linked_partitioning": "true"})
        collection = payload.get("collection", []) if isinstance(payload, dict) else payload
        return [self._track(item) for item in collection if isinstance(item, dict)]

    async def related_tracks(self, urn: str) -> list[dict[str, Any]]:
        urn = self._urn(urn, "tracks")
        payload = await self._get(f"tracks/{urn}/related", params={"access": "playable", "limit": 30, "linked_partitioning": "true"})
        collection = payload.get("collection", []) if isinstance(payload, dict) else payload
        return [self._track(item) for item in collection if isinstance(item, dict)]

    async def stream(self, urn: str) -> dict[str, str]:
        urn = self._urn(urn, "tracks")
        payload = await self._get(f"tracks/{urn}/streams")
        if isinstance(payload, dict):
            for quality in ("hls_aac_160_url", "hls_aac_96_url", "hls_mp3_128_url", "http_mp3_128_url", "hls_opus_64_url"):
                url = str(payload.get(quality) or "").strip()
                if url.startswith("https://"):
                    return {"url": url, "quality": quality}
        raise RuntimeError("Il brano non offre uno stream compatibile")

    @staticmethod
    def _urn(value: str, resource: str) -> str:
        value = str(value).strip()
        if not re.fullmatch(rf"soundcloud:{resource}:\d+", value):
            raise ValueError("Identificativo SoundCloud non valido")
        return value

    @staticmethod
    def _track(item: dict) -> dict[str, Any]:
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        artwork = str(item.get("artwork_url") or user.get("avatar_url") or "")
        return {"type": "track", "urn": str(item.get("urn") or ""), "title": str(item.get("title") or ""), "artist": str(user.get("username") or ""), "artwork": artwork, "duration": int(item.get("duration") or 0) // 1000, "permalink_url": str(item.get("permalink_url") or ""), "playable": str(item.get("access") or "playable") == "playable"}

    @staticmethod
    def _playlist(item: dict) -> dict[str, Any]:
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        return {"type": "playlist", "urn": str(item.get("urn") or ""), "title": str(item.get("title") or ""), "artist": str(user.get("username") or ""), "artwork": str(item.get("artwork_url") or user.get("avatar_url") or ""), "track_count": int(item.get("track_count") or 0), "permalink_url": str(item.get("permalink_url") or "")}

    @staticmethod
    def _user(item: dict) -> dict[str, Any]:
        return {"type": "user", "urn": str(item.get("urn") or ""), "title": str(item.get("username") or item.get("full_name") or ""), "artist": str(item.get("full_name") or ""), "artwork": str(item.get("avatar_url") or ""), "followers_count": int(item.get("followers_count") or 0), "permalink_url": str(item.get("permalink_url") or "")}
