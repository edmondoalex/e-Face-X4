import asyncio

import httpx

from app.doorbird_api import check_identity


def test_doorbird_check_requires_challenge(monkeypatch) -> None:
    requests = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            requests.append((url, kwargs))
            return httpx.Response(200, json={"BHA": {"RETURNCODE": "1"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(check_identity("192.168.2.30", 80, "user", "private"))
    assert result == {"reachable": True, "authenticated": False, "reason": "no_auth_challenge"}
    assert len(requests) == 1
    assert "private" not in requests[0][0]


def test_doorbird_check_uses_digest_after_challenge(monkeypatch) -> None:
    calls = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **kwargs):
            calls.append(kwargs)
            status = 401 if len(calls) == 1 else 200
            return httpx.Response(status, json={"BHA": {"RETURNCODE": "1"}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(check_identity("192.168.2.30", 80, "user", "private"))
    assert result == {"reachable": True, "authenticated": True, "reason": "ok"}
    assert calls[0] == {}
    assert isinstance(calls[1]["auth"], httpx.DigestAuth)
