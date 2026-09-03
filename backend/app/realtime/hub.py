"""WebSocket fan-out.

The pipeline produces alerts already addressed to a user; the hub's only job is
delivering each one to that user's open sockets. A user may have several (desktop
plus phone), so connections are tracked as a set per user id.

Delivery is best-effort by design: a dead socket is dropped, never retried. The
alert is already persisted, so a client that missed a push sees it on next load.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class ConnectionHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[Any]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: Any) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)
        logger.info("WebSocket connected for user %s", user_id)

    async def disconnect(self, user_id: int, websocket: Any) -> None:
        async with self._lock:
            self._connections.get(user_id, set()).discard(websocket)
            if not self._connections.get(user_id):
                self._connections.pop(user_id, None)
        logger.info("WebSocket disconnected for user %s", user_id)

    def connection_count(self, user_id: int | None = None) -> int:
        if user_id is not None:
            return len(self._connections.get(user_id, set()))
        return sum(len(s) for s in self._connections.values())

    async def send_to_user(self, user_id: int, payload: dict) -> int:
        """Push one payload to every socket this user has open."""
        async with self._lock:
            sockets = list(self._connections.get(user_id, set()))
        if not sockets:
            return 0

        delivered = 0
        dead: list[Any] = []
        for socket in sockets:
            try:
                await socket.send_json(payload)
                delivered += 1
            except Exception:  # noqa: BLE001 - a dropped client is normal
                dead.append(socket)

        for socket in dead:
            await self.disconnect(user_id, socket)
        return delivered

    async def broadcast(self, payloads_by_user: dict[int, list[dict]]) -> int:
        """Push a batch of per-user payloads. Returns messages delivered."""
        total = 0
        for user_id, payloads in payloads_by_user.items():
            for payload in payloads:
                total += await self.send_to_user(user_id, payload)
        return total


# Process-wide hub. Single-process is fine for the MVP; scaling to multiple API
# workers means putting Redis pub/sub behind this same interface.
hub = ConnectionHub()
