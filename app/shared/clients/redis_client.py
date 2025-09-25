import asyncio
import json
from typing import Any, Optional, Callable
from redis.asyncio import Redis
from app.config.logger import logger, JohnWickLogger, get_logger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.metrics.metrics_schema import RedisMetrics
from app.config.settings import Settings
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry


class RedisClient:
    """
    Bulletproof Redis client with:
    - Async support
    - Retries with RetryPolicy
    - TTL support
    - JSON serialization
    - Fully integrated with injected JohnWickLogger and metrics
    """

    def __init__(
        self,
        redis_url: str = Settings.redis_url,
        logger: Optional[JohnWickLogger] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.redis_url = redis_url
        self.logger: JohnWickLogger = get_logger() or logger or JohnWickLogger("RedisClient")
        self.redis: Optional[Redis] = None
        self.metrics = MetricsCollector(self.logger)
        # Retry policy: default to FixedDelayRetry if none provided
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry(max_retries=3)

    async def connect(self):
        """Connect to Redis using retry policy."""
        async def _connect():
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            self.logger.info("Connected to Redis", extra={"redis_url": self.redis_url})

        try:
            await self.retry_policy.execute(_connect)
        except Exception:
            self.logger.error("Failed to connect to Redis after retries")
            raise ConnectionError("Cannot connect to Redis")

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a key in Redis with retry policy."""
        if self.redis is None:
            await self.connect()
        payload = json.dumps(value) if isinstance(value, (dict, list)) else value

        async def _set():
            await self.redis.set(key, payload, ex=ttl)
            self.logger.info("Redis SET", extra={"key": key, "ttl": ttl, "value": value})
            self.metrics.increment(RedisMetrics.SET)

        try:
            await self.retry_policy.execute(_set)
        except Exception:
            self.logger.error("Redis SET failed after retry policy", extra={"key": key, "value": value})
            self.metrics.increment(RedisMetrics.FAILED_SET)
            self.metrics.report()
            raise

    async def get(self, key: str) -> Any:
        """Get a key from Redis with retry policy."""
        if self.redis is None:
            await self.connect()

        async def _get():
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

        try:
            return await self.retry_policy.execute(_get)
        except Exception:
            self.logger.error("Redis GET failed after retry policy", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_GET)
            self.metrics.report()
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis with retry policy."""
        if self.redis is None:
            await self.connect()

        async def _del():
            result = await self.redis.delete(key)
            self.logger.info("Redis DEL", extra={"key": key, "deleted": bool(result)})
            self.metrics.increment(RedisMetrics.DEL)
            return bool(result)

        try:
            return await self.retry_policy.execute(_del)
        except Exception:
            self.logger.error("Redis DEL failed after retry policy", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_DEL)
            self.metrics.report()
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis with retry policy."""
        if self.redis is None:
            await self.connect()

        async def _exists():
            result = bool(await self.redis.exists(key))
            self.metrics.increment(RedisMetrics.EXISTS)
            return result

        try:
            return await self.retry_policy.execute(_exists)
        except Exception:
            self.logger.error("Redis EXISTS failed after retry policy", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_EXISTS)
            self.metrics.report()
            return False

    async def close(self):
        if self.redis:
            await self.redis.close()
            self.logger.info("Redis connection closed")
