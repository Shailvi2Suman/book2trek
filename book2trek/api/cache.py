"""
Tiny cache abstraction: Redis when REDIS_URL is set, else an in-process dict
with TTLs. The voice agent hits trek search on every "find me a trek" turn, so
caching hot reads keeps end-to-end latency down — the same cache-aside pattern
you'd defend in a system-design round.
"""
from __future__ import annotations

import json
import time
from typing import Any

from .. import config as C

try:
    import redis as _redis
except Exception:  # pragma: no cover
    _redis = None


class _MemoryCache:
    """Process-local TTL cache — the fallback when Redis isn't configured."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        expires, val = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return val

    def setex(self, key: str, ttl: int, val: str) -> None:
        self._store[key] = (time.time() + ttl, val)


def _make_client():
    if C.REDIS_URL and _redis is not None:
        try:
            client = _redis.from_url(C.REDIS_URL, decode_responses=True)
            client.ping()
            return client
        except Exception:  # pragma: no cover - falls back if Redis is down
            pass
    return _MemoryCache()


_client = _make_client()


def cache_get_json(key: str) -> Any | None:
    raw = _client.get(key)
    return json.loads(raw) if raw else None


def cache_set_json(key: str, value: Any, ttl: int | None = None) -> None:
    _client.setex(key, ttl or C.CACHE_TTL_SEC, json.dumps(value))


def backend_name() -> str:
    return "redis" if isinstance(_client, getattr(_redis, "Redis", ())) else "memory"
