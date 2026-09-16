import asyncio

import pytest

from app.media_realtime import SharedMediaRealtime


class FakeConnector:
    def __init__(self) -> None:
        self.events_calls = 0
        self.snapshot_calls = 0
        self.events_queue: asyncio.Queue = asyncio.Queue()

    async def events(self):
        self.events_calls += 1
        while True:
            yield await self.events_queue.get()

    async def snapshot(self):
        self.snapshot_calls += 1
        return {"id": "evoice", "status": "online", "items": [{"id": "player"}]}


@pytest.mark.asyncio
async def test_shared_media_realtime_uses_one_stream_and_debounces_snapshots() -> None:
    connector = FakeConnector()
    broker = SharedMediaRealtime(lambda: connector, debounce_seconds=0.02)
    first = broker.subscribe(); second = broker.subscribe()
    await asyncio.sleep(0)
    assert connector.events_calls == 1
    await connector.events_queue.put({"type": "heartbeat"})
    await asyncio.sleep(0.03)
    assert connector.snapshot_calls == 0
    for _ in range(5): await connector.events_queue.put({"type": "player.updated"})
    assert (await asyncio.wait_for(first.get(), 0.2))["type"] == "media_changed"
    assert (await asyncio.wait_for(second.get(), 0.2))["type"] == "media_changed"
    assert connector.snapshot_calls == 1
    broker.unsubscribe(first); broker.unsubscribe(second)
    await broker.close()


@pytest.mark.asyncio
async def test_shared_media_snapshot_cache_prevents_parallel_upstream_requests() -> None:
    connector = FakeConnector(); broker = SharedMediaRealtime(lambda: connector)
    snapshots = await asyncio.gather(*(broker.get_snapshot() for _ in range(8)))
    assert connector.snapshot_calls == 1
    assert all(item == snapshots[0] for item in snapshots)
    await broker.close()
