import json
import hashlib
import redis.asyncio as redis
from typing import Optional, Any
from app.core.config import settings

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def make_cache_key(prefix: str, *args) -> str:
    raw = f"{prefix}:{':'.join(str(a) for a in args)}"
    return hashlib.md5(raw.encode()).hexdigest()


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    value = await r.get(key)
    if value:
        return json.loads(value)
    return None


async def cache_set(key: str, value: Any, ttl: int = settings.CACHE_TTL):
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def cache_delete(key: str):
    r = await get_redis()
    await r.delete(key)