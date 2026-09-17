from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from typing import Any, Callable


class SharedMediaRealtime:
    """One upstream media stream and snapshot cache shared by every UI client."""

    def __init__(self, connector_factory: Callable[[], Any], debounce_seconds: float = 0.35, offline_retry_seconds: float = 2.0) -> None:
        self._connector_factory = connector_factory
        self._debounce = debounce_seconds
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._stream_task: asyncio.Task | None = None
        self._snapshot_task: asyncio.Task | None = None
        self._snapshot_requested = asyncio.Event()
        self._snapshot: dict[str, Any] | None = None
        self._snapshot_checked_at = 0.0
        self._offline_retry = offline_retry_seconds
        self._snapshot_lock = asyncio.Lock()
        self._closed = False

    @property
    def snapshot_cache(self) -> dict[str, Any] | None:
        return self._snapshot

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=20)
        self._subscribers.add(queue)
        self.start()
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def start(self) -> None:
        if self._closed: return
        if self._stream_task is None or self._stream_task.done(): self._stream_task = asyncio.create_task(self._stream_loop())
        if self._snapshot_task is None or self._snapshot_task.done(): self._snapshot_task = asyncio.create_task(self._snapshot_loop())

    async def get_snapshot(self) -> dict[str, Any]:
        status = str((self._snapshot or {}).get("status") or "")
        if self._snapshot is not None and status in {"online", "stale"}: return self._snapshot
        if self._snapshot is not None and time.monotonic() - self._snapshot_checked_at < self._offline_retry: return self._snapshot
        async with self._snapshot_lock:
            status = str((self._snapshot or {}).get("status") or "")
            if self._snapshot is not None and status in {"online", "stale"}: return self._snapshot
            if self._snapshot is None or time.monotonic() - self._snapshot_checked_at >= self._offline_retry:
                self._snapshot = await self._connector_factory().snapshot()
                self._snapshot_checked_at = time.monotonic()
        return self._snapshot

    async def close(self) -> None:
        self._closed = True
        tasks = [task for task in (self._stream_task, self._snapshot_task) if task]
        for task in tasks: task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError): await task
        self._subscribers.clear()

    async def _broadcast(self, event: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                with suppress(asyncio.QueueEmpty): queue.get_nowait()
            with suppress(asyncio.QueueFull): queue.put_nowait(event)

    async def _snapshot_loop(self) -> None:
        while True:
            await self._snapshot_requested.wait()
            self._snapshot_requested.clear()
            await asyncio.sleep(self._debounce)
            self._snapshot_requested.clear()  # coalesce updates received during the debounce window
            try:
                async with self._snapshot_lock:
                    snapshot = await self._connector_factory().snapshot()
                    self._snapshot_checked_at = time.monotonic()
                if snapshot.get("status") in {"online", "stale"}:
                    self._snapshot = snapshot
                    await self._broadcast({"type": "media_changed", "event_type": "player.updated"})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.warning("evoice snapshot refresh failed: %s", type(exc).__name__)

    async def _stream_loop(self) -> None:
        backoff = (2, 4, 8, 15, 30)
        attempt = 0
        while True:
            stream = None
            try:
                stream = self._connector_factory().events()
                async for event in stream:
                    attempt = 0
                    event_type = str(event.get("type") or "")
                    if event_type == "heartbeat":
                        continue
                    if event_type in {"player.updated", "local.player_updated"}:
                        self._snapshot_requested.set()
                    else:
                        await self._broadcast({"type": "media_changed", "event_type": event_type})
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = backoff[min(attempt, len(backoff) - 1)]
                attempt += 1
                logging.warning("evoice realtime disconnected; retrying in %ss", delay)
                if stream is not None:
                    with suppress(Exception): await stream.aclose()
                    stream = None
                await asyncio.sleep(delay)
            finally:
                if stream is not None:
                    with suppress(Exception): await stream.aclose()
