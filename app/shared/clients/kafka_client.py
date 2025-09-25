import asyncio
import json
import time
from typing import Callable, Any
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from logging import Logger

# Retry Policy interface
class RetryPolicy:
    async def execute(self, func: Callable[..., Any], *args, **kwargs):
        raise NotImplementedError

# Exponential backoff retry
class ExponentialBackoffRetry(RetryPolicy):
    def __init__(self, max_retries: int = 5, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute(self, func: Callable[..., Any], *args, **kwargs):
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.base_delay * (2 ** (attempt - 1)))

# Metrics collector
class MetricsCollector:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.processed = 0
        self.dlq = 0
        self.failed_produce = 0

    def report(self):
        self.logger.info("Kafka metrics update", extra={
            "processed_messages": self.processed,
            "dlq_messages": self.dlq,
            "failed_produce": self.failed_produce
        })

# High-throughput Kafka client
class HighThroughputKafkaClient:
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        dlq_topic: str,
        group_id: str,
        logger: Logger,
        retry_policy: RetryPolicy = None,
        max_concurrency: int = 5,
        batch_size: int = 10
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.dlq_topic = dlq_topic
        self.group_id = group_id
        self.logger = logger
        self.retry_policy = retry_policy or ExponentialBackoffRetry()
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.metrics = MetricsCollector(logger)

        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self._consume_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self):
        self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self.producer.start()
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest"
        )
        await self.consumer.start()
        self.logger.info("Kafka client started")

    async def stop(self):
        self._stop_event.set()
        if self._consume_task:
            await self._consume_task
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        self.logger.info("Kafka client stopped")

    async def produce(self, key: str, value: dict):
        async def _send():
            await self.producer.send_and_wait(
                self.topic,
                key=key.encode(),
                value=json.dumps(value).encode()
            )
            self.logger.info("Message produced", extra={"key": key, "value": value})

        try:
            await self.retry_policy.execute(_send)
        except Exception:
            self.logger.error("Max retries reached, sending to DLQ", extra={"key": key, "value": value})
            self.metrics.failed_produce += 1
            await self.send_to_dlq(key, value, "Max retries reached")
        finally:
            self.metrics.report()

    async def send_to_dlq(self, key: str, value: dict, reason: str):
        dlq_message = {
            "original_key": key,
            "original_value": value,
            "reason": reason,
            "timestamp": int(time.time())
        }

        async def _send_dlq():
            await self.producer.send_and_wait(
                self.dlq_topic,
                key=key.encode(),
                value=json.dumps(dlq_message).encode()
            )
            self.metrics.dlq += 1
            self.logger.info("Sent to DLQ", extra=dlq_message)

        try:
            await self.retry_policy.execute(_send_dlq)
        except Exception:
            self.logger.error("Failed to send to DLQ after retries", extra=dlq_message)
        finally:
            self.metrics.report()

    async def _process_message(self, key: str, value: dict, callback: Callable[[str, dict], Any]):
        async with self.semaphore:
            try:
                await callback(key, value)
                self.metrics.processed += 1
                self.logger.info("Message processed", extra={"key": key, "value": value})
            except Exception as exc:
                self.logger.exception("Processing failed, sending to DLQ", extra={"key": key, "value": value})
                await self.send_to_dlq(key, value, str(exc))
            finally:
                self.metrics.report()

    async def _consume_loop(self, callback: Callable[[str, dict], Any]):
        batch = []
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

    async def consume(self, callback: Callable[[str, dict], Any]):
        """Start consuming in a background task"""
        self._consume_task = asyncio.create_task(self._consume_loop(callback))
