import asyncio
import inspect
from typing import Callable, Dict, Awaitable, Set

from app.shared.annotations.core import ApplicationScoped
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry import RetryPolicy, FixedDelayRetry
from app.shared.messaging.base import EventBus
from app.shared.clients import KafkaClient


@ApplicationScoped
class KafkaEventBus(EventBus):
    """
    Async Node.js-style EventEmitter interface over Kafka using KafkaClient.
    Handles subscriptions, publishing, and per-topic consume loops.
    """

    def __init__(
        self,
        kafka_client: KafkaClient,
        logger: JohnWickLogger = None,
        metrics: MetricsCollector = None,
        retry_policy: RetryPolicy = None,
    ):
        self.kafka_client = kafka_client
        self.logger = logger or JohnWickLogger("KafkaEventBus")
        self.metrics = metrics or self.kafka_client.metrics
        self.retry_policy = retry_policy or FixedDelayRetry(max_retries=3)

        # Subscribers per topic
        self._subscribers: Dict[str, list[Callable[[str, str, dict], Awaitable[None]]]] = {}
        self._subscriber_tasks: Dict[str, Set[asyncio.Task]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}

        self._running = False
        self._start_lock = asyncio.Lock()

    # --- Lifecycle ---
    async def start(self):
        async with self._start_lock:
            if self._running:
                return

            await self.kafka_client.start()
            self._running = True
            self.logger.info("KafkaEventBus started")

            # Start consume loops for registered topics
            for topic in self._subscribers.keys():
                if topic not in self._consume_tasks:
                    self._consume_tasks[topic] = asyncio.create_task(self._consume_loop(topic))

    async def stop(self):
        if not self._running:
            return

        # Cancel subscriber tasks
        for tasks in self._subscriber_tasks.values():
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._subscriber_tasks.clear()

        # Cancel consume loops
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

    # --- Subscribe ---
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[str, str, dict], Awaitable[None]],
    ):
        """
        Subscribe to a Kafka topic (async/await).
        Starts the bus and consume loop for the topic automatically.
        """
        await self._ensure_started()

        self._subscribers.setdefault(topic, []).append(callback)
        self.logger.info(
            "Subscription registered",
            extra={"topic": topic, "callback": callback.__name__},
        )

        # Start the consume loop for this topic if not already running
        if topic not in self._consume_tasks or self._consume_tasks[topic].done():
            self._consume_tasks[topic] = asyncio.create_task(self._consume_loop(topic))
            self.logger.info("Consume loop started for topic", extra={"topic": topic})

    # --- Publish ---
    async def publish(self, topic: str, payload: dict, key: str = "default"):
        """Publish message to Kafka via KafkaClient with retry."""
        await self._ensure_started()

        async def _publish():
            await self.kafka_client.produce(topic=topic, value=payload, key=key)

        try:
            await (self.retry_policy.execute(_publish) if self.retry_policy else _publish())
            if self.metrics:
                self.metrics.increment("published")
        except Exception as exc:
            self.logger.error("Failed to publish", extra={"topic": topic, "error": str(exc)})
            if self.metrics:
                self.metrics.increment("failed_publish")
            raise


    async def _consume_loop(self, topic: str):
        await self._ensure_started()
        self.logger.info(f"Starting consume loop for topic {topic}")

        # Subscribe KafkaClient to the topic if not already
        await self.kafka_client.subscribe_to_topics([topic])

        async for msg_topic, key, value in self.kafka_client.consume():
            if msg_topic != topic:
                continue

            tasks = set()
            for cb in self._subscribers.get(topic, []):
                async def _cb(cb=cb):
                    try:
                        # Inspect the callback signature
                        sig = inspect.signature(cb)
                        if len(sig.parameters) == 1:
                            # Only payload expected
                            await cb(value)
                        else:
                            # Expecting topic, key, value
                            await cb(msg_topic, key, value)
                    except Exception:
                        self.logger.exception("Subscriber failed", extra={"topic": topic})

                task = asyncio.create_task(_cb())
                tasks.add(task)
                task.add_done_callback(lambda t: tasks.discard(t))
            self._subscriber_tasks.setdefault(topic, set()).update(tasks)

