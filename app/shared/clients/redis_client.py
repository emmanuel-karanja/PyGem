import asyncio
import json
from typing import Any, Optional
from redis.asyncio import Redis
from app.config.logger import logger, JohnWickLogger,get_logger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.metrics.metrics_schema import RedisMetrics


class RedisClient:
    """
    Bulletproof Redis client with:
    - Async support
    - Retries with backoff
    - TTL support
    - JSON serialization
    - Fully integrated with injected JohnWickLogger and metrics
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_retries: int = 5,
        retry_backoff: float = 1.0,
        logger: Optional[JohnWickLogger] = None,
    ):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.logger: JohnWickLogger = get_logger() or logger or JohnWickLogger("RedisClient")
        self.redis: Optional[Redis] = None
        self.metrics = MetricsCollector(self.logger)

    async def connect(self):
        """Connect to Redis"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self.redis = Redis.from_url(self.redis_url, decode_responses=True)
                await self.redis.ping()
                self.logger.info("Connected to Redis", extra={"redis_url": self.redis_url})
                return
            except Exception as exc:
                self.logger.warning(
                    f"Redis connect attempt {attempt} failed",
                    extra={"error": str(exc)},
                )
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
                self.metrics.increment(RedisMetrics.SET)
                return
            except Exception as exc:
                self.logger.warning(
                    f"Redis SET attempt {attempt} failed",
                    extra={"key": key, "error": str(exc)},
                )
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis SET failed after max retries", extra={"key": key, "value": value})
        self.metrics.increment(RedisMetrics.FAILED_SET)
        self.metrics.report()

    async def get(self, key: str) -> Any:
        if self.redis is None:
            await self.connect()

        for attempt in range(1, self.max_retries + 1):
            try:
                value = await self.redis.get(key)
                if value is None:
                    self.metrics.increment(RedisMetrics.GET)
                    return None
                try:
                    deserialized = json.loads(value)
                    self.metrics.increment(RedisMetrics.GET)
                    return deserialized
                except json.JSONDecodeError:
                    self.metrics.increment(RedisMetrics.GET)
                    return value
            except Exception as exc:
                self.logger.warning(
                    f"Redis GET attempt {attempt} failed",
                    extra={"key": key, "error": str(exc)},
                )
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis GET failed after max retries", extra={"key": key})
        self.metrics.increment(RedisMetrics.FAILED_GET)
        self.metrics.report()
        return None

    async def delete(self, key: str) -> bool:
        if self.redis is None:
            await self.connect()

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.redis.delete(key)
                self.logger.info("Redis DEL", extra={"key": key, "deleted": bool(result)})
                self.metrics.increment(RedisMetrics.DEL)
                return bool(result)
            except Exception as exc:
                self.logger.warning(
                    f"Redis DEL attempt {attempt} failed",
                    extra={"key": key, "error": str(exc)},
                )
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis DEL failed after max retries", extra={"key": key})
        self.metrics.increment(RedisMetrics.FAILED_DEL)
        self.metrics.report()
        return False

    async def exists(self, key: str) -> bool:
        if self.redis is None:
            await self.connect()

        for attempt in range(1, self.max_retries + 1):
            try:
                result = bool(await self.redis.exists(key))
                self.metrics.increment(RedisMetrics.EXISTS)
                return result
            except Exception as exc:
                self.logger.warning(
                    f"Redis EXISTS attempt {attempt} failed",
                    extra={"key": key, "error": str(exc)},
                )
                await asyncio.sleep(self.retry_backoff * attempt)
        self.logger.error("Redis EXISTS failed after max retries", extra={"key": key})
        self.metrics.increment(RedisMetrics.FAILED_EXISTS)
        self.metrics.report()
        return False

    async def close(self):
        if self.redis:
            await self.redis.close()
            self.logger.info("Redis connection closed")
