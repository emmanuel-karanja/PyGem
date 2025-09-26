import asyncio
import json
import time
from typing import Callable, Any, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.metrics.metrics_schema import KafkaMetrics
from app.shared.retry.base import RetryPolicy
from app.shared.retry.fixed_delay_retry import FixedDelayRetry


class KafkaClient:
    """Async Kafka client with producer, consumer, DLQ, metrics, and concurrency control."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        dlq_topic: str,
        group_id: str,
        logger: Optional[JohnWickLogger] = None,
        retry_policy: Optional[RetryPolicy] = None,
        max_concurrency: int = 5,
        batch_size: int = 10,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.dlq_topic = dlq_topic
        self.group_id = group_id

        self.logger = logger or JohnWickLogger(name="KafkaClient")
        self.retry_policy = retry_policy or FixedDelayRetry(max_retries=3)
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_size = batch_size
        self.metrics = MetricsCollector(self.logger)

        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._consume_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start producer and consumer."""
        self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest",
        )
        await self.consumer.start()

        self.logger.info(f"Kafka client started on {self.bootstrap_servers}", extra={"topic": self.topic})

    async def stop(self):
        """Stop producer, consumer, and cancel the consume loop."""
        self._stop_event.set()

        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                self.logger.debug("Consume loop cancelled")

        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()

        self.logger.info("Kafka client stopped")

    async def produce(self, key: str, value: dict):
        """Produce message with retry and DLQ fallback."""
        async def _send():
            await self.producer.send_and_wait(
                self.topic, key=key.encode(), value=json.dumps(value).encode()
            )
            self.logger.info("Message produced", extra={"key": key, "value": value})
            self.metrics.increment(KafkaMetrics.PRODUCED)

        try:
            await self.retry_policy.execute(_send)
        except asyncio.CancelledError:
            self.logger.warning("Task was cancelled, cleaning up...")
            # Optional: close connections, unsubscribe, flush metrics
            raise
        except Exception:
            self.logger.error("Max retries reached, sending to DLQ", extra={"key": key, "value": value})
            self.metrics.increment(KafkaMetrics.FAILED_PRODUCE)
            await self.send_to_dlq(key, value, "Max retries reached")
        finally:
            self.metrics.report()

    async def send_to_dlq(self, key: str, value: dict, reason: str):
        """Send failed message to DLQ."""
        dlq_message = {
            "original_key": key,
            "original_value": value,
            "reason": reason,
            "timestamp": int(time.time()),
        }

        async def _send_dlq():
            await self.producer.send_and_wait(
                self.dlq_topic, key=key.encode(), value=json.dumps(dlq_message).encode()
            )
            self.metrics.increment(KafkaMetrics.DLQ)
            self.logger.info("Sent to DLQ", extra=dlq_message)

        try:
            await self.retry_policy.execute(_send_dlq)
        except Exception:
            self.logger.exception("Failed to send to DLQ after retries", extra=dlq_message)
        finally:
            self.metrics.report()

    async def _process_message(self, key: str, value: dict, callback: Callable[[str, dict], Any]):
        """Process a single message with semaphore and DLQ handling."""
        async with self.semaphore:
            try:
                await callback(key, value)
                self.metrics.increment(KafkaMetrics.PROCESSED)
                self.logger.info("Message processed", extra={"key": key, "value": value})
            except Exception as exc:
                self.metrics.increment(KafkaMetrics.FAILED_PROCESS)
                self.logger.exception("Processing failed, sending to DLQ", extra={"key": key, "value": value})
                await self.send_to_dlq(key, value, str(exc))
            finally:
                self.metrics.report()

    async def _consume_loop(self, callback: Callable[[str, dict], Any]):
        """Internal consume loop with batching, cancellability, and metrics."""
        batch = []
        try:
            async for msg in self.consumer:
                if self._stop_event.is_set():
                    break

                key = msg.key.decode() if msg.key else ""
                value = json.loads(msg.value.decode())
                batch.append((key, value))

                if len(batch) >= self.batch_size:
                    await asyncio.gather(*[self._process_message(k, v, callback) for k, v in batch])
                    batch.clear()

            if batch:
                await asyncio.gather(*[self._process_message(k, v, callback) for k, v in batch])
        except asyncio.CancelledError:
            self.logger.debug("Consume loop cancelled")
        except Exception as e:
            self.logger.exception(f"Error in consume loop: {e}")

    async def consume(self, callback: Callable[[str, dict], Any]):
        """Start consuming messages in the background."""
        self._stop_event.clear()
        self._consume_task = asyncio.create_task(self._consume_loop(callback))
