import asyncio
from typing import Callable, Dict, List, Optional
import json

from app.shared.event_bus.base import EventBus
from app.shared.clients import RedisClient
from app.config.logger import get_logger, JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry


class RedisEventBus(EventBus):
    """
    RedisEventBus using RedisClient for connection, retries, metrics, and JSON handling.
    Fully cancellable.
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.logger = logger or JohnWickLogger(name="RedisEventBus")
        self.redis_client = redis_client or RedisClient(logger=self.logger)

        # Channel -> list of subscriber callbacks
        self.subscribers: Dict[str, List[Callable]] = {}

        # Channel -> consume task
        self._consume_tasks: Dict[str, asyncio.Task] = {}

        # Channel -> subscriber tasks
        self._subscriber_tasks: Dict[str, set[asyncio.Task]] = {}

        # Metrics
        self.metrics: MetricsCollector = metrics or MetricsCollector(self.logger)

        # Retry policy
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry(max_retries=3)

    async def start(self):
        """Start the RedisEventBus: connect the client and initialize all subscriber channels."""
        try:
            self.logger.info("Starting RedisEventBus...")
            await self.redis_client.connect()
            self.logger.info("✅ Redis client connected")
            self.logger.info("🎉 RedisEventBus started successfully")
        except Exception as exc:
            self.logger.error("Failed to start RedisEventBus", extra={"error": str(exc)})
            raise

    async def publish(self, channel: str, payload: dict):
        """Publish a message using RedisClient with retry, metrics, and JSON serialization."""

        async def _publish():
            await self.redis_client.connect()
            await self.redis_client.redis.publish(channel, json.dumps(payload))
            self.logger.info("Published event", extra={"channel": channel, "payload": payload})
            if self.metrics:
                self.metrics.increment("published")

        try:
            await self.retry_policy.execute(_publish)
        except Exception:
            self.logger.error(
                "Failed to publish after retry policy",
                extra={"channel": channel, "payload": payload},
            )
            if self.metrics:
                self.metrics.increment("failed_publish")
            raise

    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a Redis channel using RedisClient and dispatch with retry."""

        self.subscribers.setdefault(channel, []).append(callback)

        async def consume_loop():
            await self.redis_client.connect()
            pubsub = self.redis_client.redis.pubsub()
            await pubsub.subscribe(channel)
            self.logger.info("Subscribed to Redis channel", extra={"channel": channel})
            try:
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    payload = json.loads(message["data"])

                    tasks = set()
                    for cb in self.subscribers.get(channel, []):
                        async def _cb():
                            try:
                                await cb(payload)
                            except asyncio.CancelledError:
                                self.logger.warning("Subscriber callback cancelled")
                                raise
                            except Exception as exc:
                                self.logger.exception(
                                    "Subscriber callback failed",
                                    extra={"channel": channel, "error": str(exc)},
                                )
                                if self.metrics:
                                    self.metrics.increment("failed_consume")

                        task = asyncio.create_task(self.retry_policy.execute(_cb))
                        tasks.add(task)
                        task.add_done_callback(lambda t: tasks.discard(t))

                    self._subscriber_tasks.setdefault(channel, set()).update(tasks)

                    if self.metrics:
                        self.metrics.increment("consumed")
                    self.logger.debug("Event consumed", extra={"channel": channel, "payload": payload})

            except asyncio.CancelledError:
                self.logger.info(f"Consume loop for channel {channel} cancelled")
                raise
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

        task = asyncio.create_task(consume_loop())
        self._consume_tasks[channel] = task

    async def stop(self):
        """Stop all subscriptions and close RedisClient"""

        # Cancel subscriber tasks first
        for channel, tasks in self._subscriber_tasks.items():
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        # Cancel consume loops
        for channel, task in self._consume_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"Consume task for channel {channel} cancelled")

        await self.redis_client.close()
        self.logger.info("RedisEventBus stopped")
