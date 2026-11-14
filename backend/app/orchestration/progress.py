"""WebSocket job progress broadcaster."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ProgressHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._subscribers[job_id].add(websocket)
        # Replay recent history
        for event in self._history.get(job_id, [])[-50:]:
            try:
                await websocket.send_json(event)
            except Exception:
                break

    async def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscribers[job_id].discard(websocket)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        event = {
            **event,
            "job_id": job_id,
            "timestamp": event.get("timestamp")
            or datetime.now(timezone.utc).isoformat(),
        }
        self._history[job_id].append(event)
        if len(self._history[job_id]) > 500:
            self._history[job_id] = self._history[job_id][-500:]
        dead: list[WebSocket] = []
        async with self._lock:
            sockets = list(self._subscribers.get(job_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(job_id, ws)

    def history(self, job_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(job_id, []))


progress_hub = ProgressHub()
