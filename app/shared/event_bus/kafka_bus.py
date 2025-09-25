import asyncio
from typing import Callable, Dict, Optional
from app.shared.clients import KafkaClient
from app.config.logger import JohnWickLogger, get_logger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry import RetryPolicy,FixedDelayRetry


class KafkaEventBus:
    """
    Kafka EventBus using KafkaClient for publishing, consuming, retries, DLQ, and metrics.
    Supports multiple topics and multiple subscriber callbacks per topic.
    """

    def __init__(
        self,
        kafka_client: Optional[KafkaClient] = None,
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.logger: JohnWickLogger = logger or get_logger("KafkaEventBus")
        self.kafka_client: KafkaClient = kafka_client or KafkaClient(
            bootstrap_servers="localhost:9092",
            topic="default",
            dlq_topic="dlq",
            group_id="eventbus-group",
            logger=self.logger,
        )

        # topic -> list of subscriber callbacks
        self.subscribers: Dict[str, list[Callable[[str, dict], None]]] = {}
        # topic -> consume task
        self._consume_tasks: Dict[str, asyncio.Task] = {}

        # Metrics (optional)
        self.metrics: Optional[MetricsCollector] = metrics or self.kafka_client.metrics

        # Retry policy (optional)
        self.retry_policy: Optional[RetryPolicy] = retry_policy or FixedDelayRetry()

    async def start(self):
        """Start Kafka producer and consumer"""
        await self.kafka_client.start()
        self.logger.info("KafkaEventBus started")

    async def stop(self):
        """Stop all consume tasks and Kafka client"""
        for topic, task in self._consume_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self.logger.debug(f"Consume task for topic {topic} cancelled")
        await self.kafka_client.stop()
        self.logger.info("KafkaEventBus stopped")

    async def publish(self, key: str, payload: dict, topic: Optional[str] = None):
        """
        Publish a message using KafkaClient.
        Automatically uses the client's topic if none is provided.
        """
        target_topic = topic or self.kafka_client.topic

        async def _publish():
            await self.kafka_client.produce(key, payload)

        try:
            if self.retry_policy:
                await self.retry_policy.execute(_publish)
            else:
                await _publish()

            if self.metrics:
                await self.metrics.increment("published")
        except Exception as exc:
            self.logger.error(
                "Failed to publish message",
                extra={"key": key, "topic": target_topic, "error": str(exc)},
            )
            if self.metrics:
                await self.metrics.increment("failed_publish")
            raise

    async def subscribe(self, topic: str, callback: Callable[[str, dict], None]):
        """Register a subscriber callback for a specific topic and start consuming"""
        self.subscribers.setdefault(topic, []).append(callback)
        self.logger.info("Subscriber added", extra={"topic": topic, "callback": callback.__name__})

        if topic not in self._consume_tasks:
            async def consume_loop():
                async def dispatch(key: str, value: dict):
                    # Fire-and-forget: each subscriber callback runs in its own async task
                    for cb in self.subscribers.get(topic, []):
                        async def _cb():
                            try:
                                await cb(key, value)
                            except Exception as exc:
                                self.logger.exception(
                                    "Subscriber callback failed", extra={"error": str(exc)}
                                )
                                if self.metrics:
                                    await self.metrics.increment("failed_consume")

                        if self.retry_policy:
                            asyncio.create_task(self.retry_policy.execute(_cb))
                        else:
                            asyncio.create_task(_cb())

                    if self.metrics:
                        await self.metrics.increment("consumed")

                try:
                    if self.retry_policy:
                        await self.retry_policy.execute(lambda: self.kafka_client.consume(dispatch))
                    else:
                        await self.kafka_client.consume(dispatch)
                except Exception as exc:
                    self.logger.exception("Consume loop failed", extra={"error": str(exc)})

            self._consume_tasks[topic] = asyncio.create_task(consume_loop())
