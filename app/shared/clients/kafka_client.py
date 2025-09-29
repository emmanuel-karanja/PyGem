import asyncio
import json
from typing import Optional, List, AsyncIterator, Tuple

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.admin import AIOKafkaAdminClient,NewTopic

from app.shared.annotations.core import ApplicationScoped
from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry
from app.shared.metrics.metrics_schema import KafkaMetrics


@ApplicationScoped
class KafkaClient:
    """Async Kafka client with retries, metrics, JSON support, and optional topic subscription."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = "default-group",
        topics: Optional[List[str]] = None,
        dlq_topic: Optional[str] = None,
        logger: Optional[JohnWickLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        retry_policy: Optional[RetryPolicy] = None,
        max_concurrency: int = 5,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics or []
        self.dlq_topic = dlq_topic
        self.logger = logger or JohnWickLogger("KafkaClient")
        self.metrics = metrics or MetricsCollector(self.logger)
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry(max_retries=3)
        self.max_concurrency = max_concurrency

        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False
        self._start_lock = asyncio.Lock()

    # --- Lifecycle ---
    async def start(self):
        """Start producer and consumer."""
        # Prevents trying to start the connection more than once at the same time.
        async with self._start_lock:
            if self._running:
                return

            async def _start_producer():
                self._producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
                await self._producer.start()
                self.logger.info("Kafka Producer started", extra={"bootstrap_servers": self.bootstrap_servers})

            async def _start_consumer():
                # Start consuming only if there are any topics present
                if self.topics:
                    self._consumer = AIOKafkaConsumer(
                        *self.topics,
                        bootstrap_servers=self.bootstrap_servers,
                        group_id=self.group_id,
                        auto_offset_reset="earliest",
                    )
                    await self._consumer.start()
                    self.logger.info(
                        "Kafka Consumer started", extra={"group_id": self.group_id, "topics": self.topics}
                    )

            try:
                await self.retry_policy.execute(_start_producer)
                await self.retry_policy.execute(_start_consumer)
                self._running = True
            except Exception as e:
                self.logger.error("Failed to start KafkaClient", extra={"error": str(e)})
                raise

    async def stop(self):
        """Stop producer and consumer."""
        if not self._running:
            return

        if self._consumer:
            await self._consumer.stop()
            self.logger.info("Kafka Consumer stopped")
        if self._producer:
            await self._producer.stop()
            self.logger.info("Kafka Producer stopped")

        self._running = False

    # --- Produce ---
    async def produce(self, topic: str, value: dict, key: str = "default"):
        """Publish message to Kafka with JSON encoding and retry."""
        if not self._running:
            await self.start()

        async def _produce():
            payload_bytes = json.dumps(value).encode("utf-8")
            await self._producer.send_and_wait(topic, payload_bytes, key=key.encode())
            self.metrics.increment(KafkaMetrics.PRODUCED)
            self.logger.info("Message produced", extra={"topic": topic, "key": key, "value": value})

        try:
            await self.retry_policy.execute(_produce)
        except Exception as e:
            self.logger.error(
                "Failed to produce message",
                extra={"topic": topic, "key": key, "value": value, "error": str(e)},
            )
            self.metrics.increment(KafkaMetrics.FAILED_PRODUCE)
            raise

    # --- Consume ---
    # yield messages one by one
    async def consume(self) -> AsyncIterator[Tuple[str, str, dict]]:
        """Async generator yielding messages as (topic, key, value)."""
        if not self._running:
            await self.start()
        if self._consumer is None:
            raise RuntimeError("Kafka consumer not initialized")

        try:
            # Async iteration over the messages in the consumer
            # This avoids the weird, complex,spaghettish code from earlier that used callbacks.
            # Backpressure friendly – Your loop only consumes when ready, doesn’t overwhelm downstream systems.
            # Cancel-friendly – You can stop consuming gracefully with asyncio.CancelledError.
            # Composable – Can combine multiple async iterators (e.g., consume from multiple topics or Kafka + HTTP stream) 
            #  using asyncio.gather or asyncio.create_task.
            # Metrics & logging integration – You can increment metrics inside the loop per message naturally.
            async for msg in self._consumer:
                key = msg.key.decode() if msg.key else "default"
                value = json.loads(msg.value)
                self.logger.info(f"Consumed message from kafka: {msg.topic}:{value}")
                self.metrics.increment(KafkaMetrics.PROCESSED)
                yield msg.topic, key, value
        except asyncio.CancelledError:
            self.logger.info("Kafka consume task cancelled")
            return
        except Exception as e:
            self.logger.error("Kafka consume error", extra={"error": str(e)})
            self.metrics.increment(KafkaMetrics.FAILED_PROCESS)
            raise

    # subscribe an array of topics after the client has already been started this is good for the event bus
    # a new topic will only be created if auto.create.topics.enable=true is set on the broker config
    async def subscribe_to_topics(self, topics: List[str]):
        """Subscribe the consumer to multiple topics."""
        if not self._running:
            await self.start()
        if self._consumer is None:
            raise RuntimeError("Kafka consumer not initialized")
        self._consumer.subscribe(topics)
        self.logger.info("Consumer subscribed to topics", extra={"topics": topics})
    
    # Create topics if they don't exist, this is purely for dev and experimentation, in prod, create this on the broker
    # And set the optimal replication level
    async def create_topics(self,topics: list[str],num_partitions: int = 5,replication_factor: int = 1, ):
        """
        Dynamically create Kafka topics if they don't already exist.
        """
        if not self._running:
            await self.start()  # ensure bootstrap_servers is available

        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        await admin.start()
        try:
            # Get existing topics to avoid errors
            existing = await admin.list_topics()
            new_topics = [
                NewTopic(name=t, num_partitions=num_partitions, replication_factor=replication_factor)
                for t in topics if t not in existing
            ]

            if not new_topics:
                self.logger.info("All topics already exist", extra={"topics": topics})
                return

            await admin.create_topics(new_topics)
            self.logger.info("Topics created successfully", extra={"topics": [t.name for t in new_topics]})
        except Exception as e:
            self.logger.error("Failed to create topics", extra={"error": str(e), "topics": topics})
            raise
        finally:
            await admin.close()