import asyncio
import json
from typing import Any, Optional
from redis.asyncio import Redis

from app.shared.annotations.core import ApplicationScoped
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.metrics.metrics_schema import RedisMetrics
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry


@ApplicationScoped
class RedisClient:
    """Async Redis client with retries, metrics, JSON support, and TTL."""

    def __init__(
        self,
        redis_url: str,
        logger: Optional[JohnWickLogger] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.redis_url = redis_url
        self.logger = logger or JohnWickLogger("RedisClient")
        self.redis: Optional[Redis] = None
        self.metrics = MetricsCollector(self.logger)
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry(max_retries=3)

    async def connect(self):
        """Connect to Redis and ping to verify connectivity."""
        async def _connect():
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            self.logger.info("Connected to Redis", extra={"redis_url": self.redis_url})

        try:
            await self.retry_policy.execute(_connect)
        except asyncio.CancelledError as ce:
            self.logger.warning("Task was cancelled, cleaning up...")
            raise ce
        except Exception:
            self.logger.error("Failed to connect to Redis after retries", extra={"redis_url": self.redis_url})
            raise ConnectionError(f"Cannot connect to Redis at {self.redis_url}")

    async def ping(self) -> bool:
        if self.redis is None:
            await self.connect()

        async def _ping():
            result = await self.redis.ping()
            self.logger.info("Redis PING", extra={"result": result})
            self.metrics.increment(RedisMetrics.PING)
            return result

        try:
            return await self.retry_policy.execute(_ping)
        except Exception:
            self.logger.error("Redis PING failed", extra={"redis_url": self.redis_url})
            self.metrics.increment(RedisMetrics.FAILED_PING)
            self.metrics.report()
            return False

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if self.redis is None:
            await self.connect()

        payload = json.dumps(value) if isinstance(value, (dict, list)) else value

        async def _set():
            await self.redis.set(key, payload, ex=ttl)
            self.logger.info("Redis SET", extra={"key": key, "ttl": ttl, "value": value})
            self.metrics.increment(RedisMetrics.SET)

        try:
            await self.retry_policy.execute(_set)
        except Exception as e:
            self.logger.error("Redis SET failed after retries", extra={"key": key, "value": value})
            self.metrics.increment(RedisMetrics.FAILED_SET)
            self.metrics.report()
            raise e

    async def get(self, key: str) -> Any:
        if self.redis is None:
            await self.connect()

        async def _get():
            value = await self.redis.get(key)
            self.metrics.increment(RedisMetrics.GET)
            if value is None:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        try:
            return await self.retry_policy.execute(_get)
        except Exception:
            self.logger.error("Redis GET failed after retries", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_GET)
            self.metrics.report()
            return None

    async def delete(self, key: str) -> bool:
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
            self.logger.error("Redis DEL failed after retries", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_DEL)
            self.metrics.report()
            return False

    async def exists(self, key: str) -> bool:
        if self.redis is None:
            await self.connect()

        async def _exists():
            result = bool(await self.redis.exists(key))
            self.metrics.increment(RedisMetrics.EXISTS)
            return result

        try:
            return await self.retry_policy.execute(_exists)
        except Exception:
            self.logger.error("Redis EXISTS failed after retries", extra={"key": key})
            self.metrics.increment(RedisMetrics.FAILED_EXISTS)
            self.metrics.report()
            return False

    async def close(self):
        if self.redis:
            await self.redis.close()
            self.logger.info("Redis connection closed")
