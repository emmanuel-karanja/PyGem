import asyncio
from typing import Callable, Dict, Awaitable, Optional

from app.shared.clients import KafkaClient
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry import RetryPolicy, FixedDelayRetry


class KafkaEventBus:
    """
    Node.js EventEmitter-like interface over Kafka.
    Accepts a KafkaClient from EventBusFactory for DI-friendly usage.
    """

    def __init__(
        self,
        kafka_client: KafkaClient,
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.logger = logger or JohnWickLogger(name="KafkaEventBus")
        self.kafka_client = kafka_client

        self._subscribers: Dict[str, list[Callable[[str, dict], Awaitable[None]]]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}
        self._subscriber_tasks: Dict[str, set[asyncio.Task]] = {}

        self.metrics = metrics or self.kafka_client.metrics
        self.retry_policy = retry_policy or FixedDelayRetry(max_retries=3)

        self._running = False
        self._start_lock = asyncio.Lock()

    # --- Lifecycle ---
    async def start(self):
        async with self._start_lock:
            if not self._running:
                await self.kafka_client.start()
                self._running = True
                self.logger.info("KafkaEventBus started")

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
            await asyncio.gather(task, return_exceptions=True)
        self._consume_tasks.clear()

        await self.kafka_client.stop()
        self._running = False
        self.logger.info("KafkaEventBus stopped")

    async def _ensure_started(self):
        if not self._running:
            await self.start()

    # --- Node.js-style API ---
    def on(self, topic: str, callback: Callable[[str, dict], Awaitable[None]]):
        async def _setup():
            await self._ensure_started()
            self._subscribers.setdefault(topic, []).append(callback)
            self.logger.info(
                "Subscriber added", extra={"topic": topic, "callback": callback.__name__}
            )

            if topic not in self._consume_tasks:
                self._consume_tasks[topic] = asyncio.create_task(self._consume_loop(topic))

        asyncio.create_task(_setup())

    #alias
    subscribe = on

    async def emit(self, topic: str, payload: dict, key: str = "default"):
        await self._ensure_started()

        async def _publish():
            await self.kafka_client.produce(key, payload)

        try:
            if self.retry_policy:
                await self.retry_policy.execute(_publish)
            else:
                await _publish()

            if self.metrics:
                self.metrics.increment("published")
        except Exception as exc:
            self.logger.error("Failed to publish", extra={"topic": topic, "error": str(exc)})
            if self.metrics:
                self.metrics.increment("failed_publish")
            raise
    # alias
    publish=emit
    async def _consume_loop(self, topic: str):
        async def dispatch(key: str, value: dict):
            tasks = set()
            for cb in self._subscribers.get(topic, []):
                async def _cb():
                    try:
                        await cb(key, value)
                    except Exception as exc:
                        self.logger.exception("Subscriber failed", extra={"error": str(exc)})
                        if self.metrics:
                            self.metrics.increment("failed_consume")

                task = (
                    asyncio.create_task(self.retry_policy.execute(_cb))
                    if self.retry_policy
                    else asyncio.create_task(_cb())
                )

                tasks.add(task)
                task.add_done_callback(lambda t: tasks.discard(t))

            self._subscriber_tasks.setdefault(topic, set()).update(tasks)

            if self.metrics:
                self.metrics.increment("consumed")

        try:
            await self.kafka_client.consume(dispatch)
        except asyncio.CancelledError:
            self.logger.debug(f"Consume loop for {topic} cancelled")
            raise
        except Exception as exc:
            self.logger.exception(
                "Consume loop error", extra={"topic": topic, "error": str(exc)}
            )
