"""Thin Redis cache wrapper that degrades to a no-op when Redis is down."""

from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            str(settings.REDIS_URL), decode_responses=True, socket_timeout=2
        )
    return _client


def cache_get(key: str) -> Any | None:
    try:
        raw = get_client().get(key)
    except redis.RedisError as exc:
        logger.warning("cache_get_failed", key=key, error=str(exc))
        return None
    return json.loads(raw) if isinstance(raw, str | bytes) else None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    try:
        get_client().setex(key, ttl or settings.CACHE_TTL_SECONDS, json.dumps(value, default=str))
    except redis.RedisError as exc:
        logger.warning("cache_set_failed", key=key, error=str(exc))


def cache_invalidate(pattern: str) -> None:
    try:
        client = get_client()
        for key in client.scan_iter(match=pattern, count=500):
            client.delete(key)
    except redis.RedisError as exc:
        logger.warning("cache_invalidate_failed", pattern=pattern, error=str(exc))


def ping() -> bool:
    try:
        return bool(get_client().ping())
    except redis.RedisError:
        return False
