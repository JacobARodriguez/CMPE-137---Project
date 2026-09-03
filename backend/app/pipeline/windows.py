"""Catalyst confirmation-window state.

A catalyst stays eligible for technical confirmation until its window expires.
That state is hot, small, and shared across workers, which is what Redis is for
in the target architecture -- but the in-memory store means the pipeline runs
with no Redis installed, so tests and offline dev need no infrastructure.

Both stores implement the same `WindowStore` protocol; the runner cannot tell
them apart.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain import Catalyst, CatalystSource, CatalystType, Direction, utcnow

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "confluence:windows:"


@runtime_checkable
class WindowStore(Protocol):
    async def open_window(self, catalyst: Catalyst) -> None: ...

    async def active(self, ticker: str, now: datetime | None = None) -> list[Catalyst]: ...

    async def close(self, ticker: str, catalyst_id: str) -> None: ...

    async def purge_expired(self, now: datetime | None = None) -> int: ...


def _catalyst_key(catalyst: Catalyst) -> str:
    """Stable identity so re-detecting the same event does not duplicate it."""
    return (
        f"{catalyst.ticker}:{catalyst.type.value}:"
        f"{catalyst.headline}:{int(catalyst.window_expires_at.timestamp())}"
    )


def _to_json(catalyst: Catalyst) -> str:
    return json.dumps(
        {
            "id": catalyst.id,
            "ticker": catalyst.ticker,
            "type": catalyst.type.value,
            "source": catalyst.source.value,
            "direction": catalyst.direction.value,
            "magnitude": catalyst.magnitude,
            "materiality": catalyst.materiality,
            "detected_at": catalyst.detected_at.isoformat(),
            "window_expires_at": catalyst.window_expires_at.isoformat(),
            "headline": catalyst.headline,
            "payload": catalyst.payload,
        }
    )


def _from_json(raw: str) -> Catalyst:
    d = json.loads(raw)
    return Catalyst(
        id=d["id"],
        ticker=d["ticker"],
        type=CatalystType(d["type"]),
        source=CatalystSource(d["source"]),
        direction=Direction(d["direction"]),
        magnitude=d["magnitude"],
        materiality=d["materiality"],
        detected_at=datetime.fromisoformat(d["detected_at"]),
        window_expires_at=datetime.fromisoformat(d["window_expires_at"]),
        headline=d["headline"],
        payload=d["payload"],
    )


class InMemoryWindowStore:
    """Process-local window state. The default; no infrastructure required."""

    def __init__(self) -> None:
        self._by_ticker: dict[str, dict[str, Catalyst]] = defaultdict(dict)

    async def open_window(self, catalyst: Catalyst) -> None:
        key = _catalyst_key(catalyst)
        catalyst.id = catalyst.id or key
        self._by_ticker[catalyst.ticker][key] = catalyst

    async def active(self, ticker: str, now: datetime | None = None) -> list[Catalyst]:
        now = now or utcnow()
        return [c for c in self._by_ticker.get(ticker, {}).values() if not c.expired(now)]

    async def close(self, ticker: str, catalyst_id: str) -> None:
        self._by_ticker.get(ticker, {}).pop(catalyst_id, None)

    async def purge_expired(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        removed = 0
        for ticker, windows in self._by_ticker.items():
            expired = [k for k, c in windows.items() if c.expired(now)]
            for k in expired:
                windows.pop(k, None)
                removed += 1
        return removed


class RedisWindowStore:
    """Shared window state so multiple API/worker processes agree.

    Each ticker gets a hash of open catalysts. Redis TTL is set past the longest
    window so abandoned keys expire on their own; `purge_expired` still runs to
    drop individual entries promptly.
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def _key(self, ticker: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{ticker}"

    async def open_window(self, catalyst: Catalyst) -> None:
        key = _catalyst_key(catalyst)
        catalyst.id = catalyst.id or key
        await self._redis.hset(self._key(catalyst.ticker), key, _to_json(catalyst))
        # Longest configured window is 24h; give the key generous headroom.
        await self._redis.expire(self._key(catalyst.ticker), 60 * 60 * 36)

    async def active(self, ticker: str, now: datetime | None = None) -> list[Catalyst]:
        now = now or utcnow()
        raw = await self._redis.hgetall(self._key(ticker))
        out: list[Catalyst] = []
        for value in raw.values():
            if isinstance(value, bytes):
                value = value.decode()
            try:
                catalyst = _from_json(value)
            except (ValueError, KeyError):
                logger.warning("Discarding malformed window entry for %s", ticker)
                continue
            if not catalyst.expired(now):
                out.append(catalyst)
        return out

    async def close(self, ticker: str, catalyst_id: str) -> None:
        await self._redis.hdel(self._key(ticker), catalyst_id)

    async def purge_expired(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        removed = 0
        async for key in self._redis.scan_iter(match=f"{_REDIS_KEY_PREFIX}*"):
            ticker_key = key.decode() if isinstance(key, bytes) else key
            raw = await self._redis.hgetall(ticker_key)
            for field, value in raw.items():
                if isinstance(value, bytes):
                    value = value.decode()
                try:
                    if _from_json(value).expired(now):
                        await self._redis.hdel(ticker_key, field)
                        removed += 1
                except (ValueError, KeyError):
                    await self._redis.hdel(ticker_key, field)
                    removed += 1
        return removed


async def build_window_store(redis_url: str | None) -> WindowStore:
    """Redis when configured and reachable, in-memory otherwise."""
    if not redis_url:
        return InMemoryWindowStore()
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        logger.info("Catalyst windows backed by Redis at %s", redis_url)
        return RedisWindowStore(client)
    except Exception:  # noqa: BLE001 - Redis is optional; degrade cleanly
        logger.warning(
            "Redis unavailable at %s; using in-memory window store", redis_url,
            exc_info=True,
        )
        return InMemoryWindowStore()
