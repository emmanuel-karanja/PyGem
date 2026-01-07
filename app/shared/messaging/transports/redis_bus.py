import asyncio
import json
from typing import Callable, Dict, List, Optional, Awaitable
import redis.asyncio as aioredis

from app.shared.messaging import EventBus
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry
from app.shared.annotations import ApplicationScoped


@ApplicationScoped
class RedisEventBus(EventBus):
    """Redis Pub/Sub. Directly manages Redis connections for Pub/Sub only.
       Why?
       1. Once a connection issues a SUBSCRIBE or PSUBSCRIBE command, that connection becomes dedicated to Pub/Sub.
       2. Redis will only send you Pub/Sub messages over that connection — it will no longer accept normal commands (like GET/SET).
       3. This is by design so messages can be delivered in real time without being blocked by command round-trips.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.logger = logger or JohnWickLogger(name="RedisEventBus")
        self.redis_url = redis_url

        # Dedicated connections
        self.publisher = None
        self.subscriber = None

        self.subscribers: Dict[str, List[Callable[[dict], Awaitable[None]]]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}
        self._subscriber_tasks: Dict[str, set[asyncio.Task]] = {}

        self.metrics = metrics or MetricsCollector(self.logger)
        self.retry_policy = retry_policy or FixedDelayRetry(max_retries=3)

        self._running = False
        self._start_lock = asyncio.Lock()

    async def start(self):
        async with self._start_lock:
            if not self._running:
                self.publisher = aioredis.from_url(self.redis_url)
                self.subscriber = aioredis.from_url(self.redis_url)
                self._running = True
                self.logger.info("RedisEventBus started")

    async def stop(self):
        if not self._running:
            return

        for tasks in self._subscriber_tasks.values():
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._subscriber_tasks.clear()

        for task in self._consume_tasks.values():
            task.cancel()
        await asyncio.gather(*self._consume_tasks.values(), return_exceptions=True)
        self._consume_tasks.clear()

        if self.publisher:
            await self.publisher.close()
        if self.subscriber:
            await self.subscriber.close()

        self._running = False
        self.logger.info("RedisEventBus stopped")

    async def _ensure_started(self):
        if not self._running:
            await self.start()

    async def subscribe(self, channel: str, callback: Callable[[dict], Awaitable[None]]):
        await self._ensure_started()
        self.subscribers.setdefault(channel, []).append(callback)

        if channel not in self._consume_tasks:
            # the pattern of creating a task for a _consume_loop and a _consume_loop per channel
            self._consume_tasks[channel] = asyncio.create_task(self._consume_loop(channel))
        self.logger.info("Subscription registered", extra={"channel": channel})

    async def publish(self, channel: str, payload: dict):
        await self._ensure_started()

        async def _publish():
            self.logger.info(f"Publishing message to redis:{channel}: {payload}")
            await self.publisher.publish(channel, json.dumps(payload))

        try:
            await self.retry_policy.execute(_publish)
            if self.metrics:
                self.metrics.increment("published")
        except Exception:
            self.logger.error("Failed to publish", extra={"channel": channel})
            if self.metrics:
                self.metrics.increment("failed_publish")
            raise

    async def _consume_loop(self, channel: str):
        while self._running:
            try:
                pubsub = self.subscriber.pubsub()
                await pubsub.subscribe(channel)
                self.logger.info("Subscribed", extra={"channel": channel})

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] != "message":
                        continue

                    payload = json.loads(message["data"])

                    tasks = set()
                    for cb in self.subscribers.get(channel, []):
                        async def _cb(cb=cb):
                            try:
                                await cb(payload)
                            except Exception as exc:
                                self.logger.exception(
                                    "Subscriber failed", extra={"error": str(exc)}
                                )
                                if self.metrics:
                                    self.metrics.increment("failed_consume")
                       # Again a task for each callback execution.
                        task = asyncio.create_task(self.retry_policy.execute(_cb))
                        tasks.add(task)
                        task.add_done_callback(lambda t: tasks.discard(t))

                    if tasks:
                        self._subscriber_tasks.setdefault(channel, set()).update(tasks)

                    if self.metrics:
                        self.metrics.increment("consumed")

            except asyncio.CancelledError:
                self.logger.debug(f"Consume loop for {channel} cancelled")
                break
            except Exception as exc:
                self.logger.warning(
                    f"Consume loop error for channel={channel}, retrying...",
                    extra={"error": str(exc)},
                )
                try:
                    await self.retry_policy.execute(lambda: self.subscriber.ping())
                except Exception:
                    self.logger.error("Reconnect failed, stopping consumer")
                    break
                await asyncio.sleep(1)
            finally:
                try:
                    if "pubsub" in locals():
                        await pubsub.unsubscribe(channel)
                        await pubsub.close()
                except Exception:
                    pass
