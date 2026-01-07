import asyncio
import inspect
import os
from typing import Callable, Dict, Awaitable, Set

from app.shared.annotations import ApplicationScoped
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry import RetryPolicy, FixedDelayRetry
from app.shared.messaging.base import EventBus
from app.shared.clients import KafkaClient
from app.shared.metrics.metrics_schema import KafkaMetrics


@ApplicationScoped #singleton
class KafkaEventBus(EventBus):
    """
    Async EventBus ontop of Kafka using KafkaClient.
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

       
        self._subscribers: Dict[str, list[Callable[[str, str, dict], Awaitable[None]]]] = {}
        self._subscriber_tasks: Dict[str, Set[asyncio.Task]] = {} #tasks to run callbacks for the subscribers mapped by topic
        self._consume_tasks: Dict[str, asyncio.Task] = {}  #one task per topic for the consume loop i.e a collection of consume_loop tasks

        self._running = False
        self._start_lock = asyncio.Lock()

    # --- Lifecycle ---
    async def start(self):
        async with self._start_lock:
            if self._running:
                return

            await self.kafka_client.start()
            self._running = True
            self.logger.info("KafkaEventBus started...")

            # Start consume loops for registered topics 
            # Subscribers per topic, do not start a new consume_loop task if there is already one running for a given topic
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

    async def _ensure_topic_exists(self, topic: str):
        """
        Create topic in dev environment using KafkaClient helper.
        """
        env = os.getenv("APP_ENV", "dev")  # default to dev
        if env != "dev":
            return  # Only create topics in dev

        # Use KafkaClient's method to create topic
        await self.kafka_client.create_topics([topic])

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
        
        # DEV: ensure topic exists
        await self._ensure_topic_exists(topic)
        
        self._subscribers.setdefault(topic, []).append(callback)
        self.logger.info(
            "Subscription registered",
            extra={"topic": topic, "callback": callback.__name__},
        )

        # Start the consume loop for this topic if not already running
        if topic not in self._consume_tasks or self._consume_tasks[topic].done():
            # Each topic has its own _consume_loop running and within each, we will have a task for each callback
            # think of it as a tree. i.e. if you have n topics, you'll have n _consume_loop tasks and if you have m subscribers
            # per topic, you'll have m _subscriber_tasks. We keep track of all of them.
            self._consume_tasks[topic] = asyncio.create_task(self._consume_loop(topic))
            self.logger.info("Consume loop started for topic", extra={"topic": topic})

    # --- Publish ---
    async def publish(self, topic: str, payload: dict, key: str = "default"):
        """Publish message to Kafka via KafkaClient with retry."""
        await self._ensure_started()

        async def _publish():
            await self.kafka_client.produce(topic=topic, value=payload, key=key)

        try:
            # do retries only if a retry policy has been set else, just call _publish directly
            await (self.retry_policy.execute(_publish) if self.retry_policy else _publish())
            if self.metrics:
                self.metrics.increment(KafkaMetrics.PRODUCED)
        except Exception as exc:
            self.logger.error("Failed to publish", extra={"topic": topic, "error": str(exc)})
            if self.metrics:
                self.metrics.increment(KafkaMetrics.FAILED_PRODUCE)
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
            # create a task for each callback for the message and schedule it
            # the _subscribers maps a topic to callbacks i.e. a topic has an array of callbacks
            for cb in self._subscribers.get(topic, []):
                # wrap it
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
                # a callback task is discarded as soon as it completes execution.
                task.add_done_callback(lambda t: tasks.discard(t))
                #subscribe_tasks has the tasks, they are shortlived, the _consume_loop tasks on the other hand live long.
            self._subscriber_tasks.setdefault(topic, set()).update(tasks)

