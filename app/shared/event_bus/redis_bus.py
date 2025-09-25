import asyncio
import json
from typing import Callable, Dict, List, Optional
from redis.asyncio import Redis

from app.shared.event_bus.base import EventBus
from app.config.logger import get_logger, BulletproofLogger
from app.shared.metrics.metrics_collector import MetricsCollector


class RedisEventBus(EventBus):
    """
    Redis-based EventBus implementation using Redis PUB/SUB.
    Supports async publishing/subscribing, retries, and structured logging.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_retries: int = 3,
        logger: Optional[BulletproofLogger] = None,
    ):
        self.redis_url = redis_url
        self.max_retries = max_retries
        self.logger: BulletproofLogger = logger or get_logger("RedisEventBus")
        self.redis: Optional[Redis] = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}
        self.metrics = MetricsCollector(self.logger)

    async def connect(self):
        """Connect to Redis"""
        if not self.redis:
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            try:
                await self.redis.ping()
                self.logger.info("Connected to Redis", extra={"redis_url": self.redis_url})
            except Exception as exc:
                self.logger.error("Failed to connect to Redis", extra={"error": str(exc)})
                raise

    async def publish(self, channel: str, payload: dict):
        """Publish a message to a Redis channel with retries"""
        await self.connect()
        data = json.dumps(payload)
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.redis.publish(channel, data)
                self.logger.info("Published event to Redis", extra={"channel": channel, "payload": payload})
                self.metrics.increment("published")
                return
            except Exception as exc:
                self.logger.warning(
                    f"Publish attempt {attempt} failed",
                    extra={"channel": channel, "error": str(exc)}
                )
                await asyncio.sleep(0.5 * attempt)
        self.logger.error("Failed to publish after retries", extra={"channel": channel, "payload": payload})
        self.metrics.increment("failed_publish")

    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a Redis channel"""
        await self.connect()
        self.subscribers.setdefault(channel, []).append(callback)

        async def consume_loop():
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            self.logger.info("Subscribed to Redis channel", extra={"channel": channel})
            try:
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    try:
                        payload = json.loads(message["data"])
                        for cb in self.subscribers.get(channel, []):
                            asyncio.create_task(cb(payload))
                        self.metrics.increment("consumed")
                        self.logger.debug("Event consumed", extra={"channel": channel, "payload": payload})
                    except Exception as exc:
                        self.logger.exception("Failed to process message", extra={"channel": channel, "error": str(exc)})
                        self.metrics.increment("failed_consume")
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

        task = asyncio.create_task(consume_loop())
        self._consume_tasks[channel] = task

    async def stop(self):
        """Stop all subscriptions and Redis connection"""
        for channel, task in self._consume_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"Consume task for channel {channel} cancelled")

        if self.redis:
            await self.redis.close()
            self.logger.info("Redis connection closed")
