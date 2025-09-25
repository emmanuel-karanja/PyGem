import asyncio
import json
import aioredis
from typing import Any, Optional, Callable

class RedisClient:
    """
    Bulletproof Redis client with:
    - Async support
    - Retries
    - TTL support
    - JSON serialization
    - Fully integrated with injected BulletproofLogger
    """
    def __init__(
        self,
        redis_url: str = "redis://localhost",
        max_retries: int = 5,
        retry_backoff: float = 1.0,
        logger: Logger | None = None
    ):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.logger = logger or logging.getLogger("RedisClient")
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
                self.logger.info("Connected to Redis", extra={"redis_url": self.redis_url})
                return
            except Exception as exc:
                self.logger.warning(f"Redis connect attempt {attempt} failed", extra={"error": str(exc)})
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Failed to connect to Redis after max retries")
        raise ConnectionError("Cannot connect to Redis")

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if self.redis is None:
            await self.connect()
        payload = json.dumps(value) if isinstance(value, (dict, list)) else value
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.redis.set(key, payload, ex=ttl)
                self.logger.info("Redis SET", extra={"key": key, "ttl": ttl, "value": value})
                return
            except Exception as exc:
                self.logger.warning(f"Redis SET attempt {attempt} failed", extra={"key": key, "error": str(exc)})
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis SET failed after max retries", extra={"key": key, "value": value})

    async def get(self, key: str) -> Any:
        if self.redis is None:
            await self.connect()
        for attempt in range(1, self.max_retries + 1):
            try:
                value = await self.redis.get(key)
                if value is None:
                    return None
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            except Exception as exc:
                self.logger.warning(f"Redis GET attempt {attempt} failed", extra={"key": key, "error": str(exc)})
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis GET failed after max retries", extra={"key": key})
        return None

    async def delete(self, key: str) -> bool:
        if self.redis is None:
            await self.connect()
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.redis.delete(key)
                self.logger.info("Redis DEL", extra={"key": key, "deleted": bool(result)})
                return bool(result)
            except Exception as exc:
                self.logger.warning(f"Redis DEL attempt {attempt} failed", extra={"key": key, "error": str(exc)})
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis DEL failed after max retries", extra={"key": key})
        return False

    async def exists(self, key: str) -> bool:
        if self.redis is None:
            await self.connect()
        for attempt in range(1, self.max_retries + 1):
            try:
                return bool(await self.redis.exists(key))
            except Exception as exc:
                self.logger.warning(f"Redis EXISTS attempt {attempt} failed", extra={"key": key, "error": str(exc)})
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis EXISTS failed after max retries", extra={"key": key})
        return False

    async def close(self):
        if self.redis:
            await self.redis.close()
            self.logger.info("Redis connection closed")
