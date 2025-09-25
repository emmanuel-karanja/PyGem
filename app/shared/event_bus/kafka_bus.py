import asyncio
import json
from typing import Callable, Dict, List, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.config.logger import JohnWickLogger, get_logger
from app.shared.metrics.metrics_collector import MetricsCollector


class KafkaEventBus:
    """
    Kafka EventBus with:
    - Async producer and consumer
    - Retry support
    - DLQ handling
    - Structured logging
    - Safe fire-and-forget subscriber callbacks
    """

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = "eventbus-group",
        dlq_topic: Optional[str] = None,
        max_retries: int = 5,
        logger: Optional[JohnWickLogger] = None,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.dlq_topic = dlq_topic
        self.max_retries = max_retries
        self.logger: JohnWickLogger = logger or get_logger("KafkaEventBus")

        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self._consume_tasks: Dict[str, asyncio.Task] = {}
        self.metrics = MetricsCollector(self.logger)

    async def start_producer(self):
        """Start the Kafka producer if not already started"""
        if not self.producer:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            await self.producer.start()
            self.logger.info("Kafka producer started", extra={"servers": self.bootstrap_servers})

    async def stop(self):
        """Stop all consume tasks, consumer, and producer"""
        for topic, task in self._consume_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"Consume task for topic {topic} cancelled")

        if self.consumer:
            await self.consumer.stop()
            self.logger.info("Kafka consumer stopped")

        if self.producer:
            await self.producer.stop()
            self.logger.info("Kafka producer stopped")

        self.logger.info("KafkaEventBus fully stopped")

    async def _send_with_retry(self, topic: str, payload: dict):
        """Internal helper to send message with retries and DLQ fallback"""
        await self.start_producer()
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.producer.send_and_wait(
                    topic=topic,
                    key=None,
                    value=json.dumps(payload).encode(),
                )
                self.logger.info("Event published", extra={"topic": topic, "payload": payload, "attempt": attempt})
                self.metrics.success()
                return
            except Exception as exc:
                self.logger.warning(
                    "Publish attempt failed",
                    extra={"topic": topic, "error": str(exc), "attempt": attempt},
                )
                await asyncio.sleep(0.5 * attempt)

        # Send to DLQ if configured
        if self.dlq_topic:
            dlq_payload = {"original_topic": topic, "payload": payload, "reason": "Max retries reached"}
            try:
                await self.producer.send_and_wait(
                    topic=self.dlq_topic,
                    key=None,
                    value=json.dumps(dlq_payload).encode(),
                )
                self.logger.error("Sent message to DLQ", extra={"dlq_topic": self.dlq_topic, "payload": dlq_payload})
                self.metrics.failure()
            except Exception as exc:
                self.logger.exception("Failed to send to DLQ", extra={"error": str(exc)})
                self.metrics.failure()
        else:
            self.logger.error("Failed to publish message and no DLQ configured", extra={"topic": topic, "payload": payload})
            self.metrics.failure()

        self.metrics.report()

    async def publish(self, event_name: str, payload: dict):
        """Public publish method"""
        await self._send_with_retry(event_name, payload)

    async def subscribe(self, event_name: str, callback: Callable):
        """Subscribe to a Kafka topic and start consuming messages"""
        if not self.consumer:
            self.consumer = AIOKafkaConsumer(
                event_name,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset="earliest",
            )
            await self.consumer.start()

        self.subscribers.setdefault(event_name, []).append(callback)
        self.logger.info("Subscribed to Kafka topic", extra={"topic": event_name, "group_id": self.group_id})

        async def consume_loop():
            async for msg in self.consumer:
                try:
                    payload = json.loads(msg.value.decode())
                    for cb in self.subscribers.get(event_name, []):
                        asyncio.create_task(cb(payload))
                    self.logger.debug("Event consumed", extra={"topic": event_name, "payload": payload})
                    self.metrics.success()
                except Exception as exc:
                    self.logger.exception("Failed to process consumed event", extra={"topic": event_name, "error": str(exc)})
                    self.metrics.failure()
                finally:
                    self.metrics.report()

        # Track consume task for clean shutdown
        task = asyncio.create_task(consume_loop())
        self._consume_tasks[event_name] = task
