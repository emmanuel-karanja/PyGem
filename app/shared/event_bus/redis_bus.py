import asyncio
from typing import Callable, Dict, List, Optional
import json

from app.shared.event_bus.base import EventBus
from app.shared.clients import RedisClient
from app.config.logger import get_logger, JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector


class RedisEventBus(EventBus):
    """
    RedisEventBus using RedisClient for connection, retries, metrics, and JSON handling.
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        max_retries: int = 3,
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        self.logger = logger or get_logger("RedisEventBus")
        self.redis_client = redis_client or RedisClient(logger=self.logger)
        self.max_retries = max_retries

        # Channel -> list of subscriber callbacks
        self.subscribers: Dict[str, List[Callable]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}

        # Use the same metrics as the client
        self.metrics: MetricsCollector = metrics or MetricsCollector(self.logger)
      
    async def start(self):
        """
        Start the RedisEventBus: connect the client and initialize all subscriber channels.
        """
        try:
            self.logger.info("Starting RedisEventBus...")
            await self.redis_client.connect()
            self.logger.info("✅ Redis client connected")

            # Start all existing subscriptions (if any)
            for channel, callbacks in self.subscribers.items():
                self.logger.info(f"Initializing subscriber(s) for channel '{channel}'")
                await self.subscribe(channel, lambda payload: None)  # no-op default callback

            self.logger.info("🎉 RedisEventBus started successfully")
        except Exception as exc:
            self.logger.error("Failed to start RedisEventBus", extra={"error": str(exc)})
            raise

    async def publish(self, channel: str, payload: dict):
        """
        Publish a message using RedisClient with retries, metrics, and JSON serialization.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.redis_client.connect()
                # RedisClient handles JSON serialization
                await self.redis_client.redis.publish(channel, json.dumps(payload))
                self.logger.info("Published event", extra={"channel": channel, "payload": payload})
                await self.metrics.increment("published")
                return
            except Exception as exc:
                self.logger.warning(
                    f"Publish attempt {attempt} failed",
                    extra={"channel": channel, "error": str(exc)},
                )
                await asyncio.sleep(0.5 * attempt)

        self.logger.error("Failed to publish after max retries", extra={"channel": channel, "payload": payload})
        self.metrics.increment("failed_publish")

    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a Redis channel using RedisClient"""
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
                    try:
                        payload = json.loads(message["data"])
                        for cb in self.subscribers.get(channel, []):
                            # Dispatch each callback in its own async task
                            asyncio.create_task(cb(payload))
                        if(self.metrics):
                            self.metrics.increment("consumed")
                        self.logger.debug("Event consumed", extra={"channel": channel, "payload": payload})
                    except Exception as exc:
                        self.logger.exception("Failed to process message", extra={"channel": channel, "error": str(exc)})
                        await self.metrics.increment("failed_consume")
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

        task = asyncio.create_task(consume_loop())
        self._consume_tasks[channel] = task

    async def stop(self):
        """Stop all subscriptions and close RedisClient"""
        for channel, task in self._consume_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"Consume task for channel {channel} cancelled")

        await self.redis_client.close()
        self.logger.info("RedisEventBus stopped")
