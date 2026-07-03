from __future__ import annotations

import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class InMemoryStore:
    """Fallback store when Redis/Postgres are unavailable."""

    def __init__(self) -> None:
        self._kv: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._kv[key] = json.dumps(value)

    async def get_json(self, key: str) -> Any | None:
        raw = self._kv.get(key)
        return json.loads(raw) if raw else None

    async def sadd(self, key: str, member: str) -> bool:
        bucket = self._sets.setdefault(key, set())
        if member in bucket:
            return False
        bucket.add(member)
        return True
