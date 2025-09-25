import asyncio
import json
import time
from typing import Callable, Any, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from app.config.logger import JohnWickLogger, get_logger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.metrics.metrics_schema import KafkaMetrics
from retry.base import RetryPolicy
from retry.fixed_delay_retry import FixedDelayRetry



class KafkaClient:
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

        self.logger: JohnWickLogger = logger or get_logger("KafkaClient")
        self.retry_policy = retry_policy or FixedDelayRetry(max_retries=3)
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.metrics = MetricsCollector(self.logger)

        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._consume_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        try:
            self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
            self.logger.info(self.bootstrap_servers)
            await self.producer.start()
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset="earliest",
            )
            await self.consumer.start()
            self.logger.info("Kafka client started", extra={"topic": self.topic})
        except Exception as e:
            self.logger.error(f"Failed to start Kafka client: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        try:
            self._stop_event.set()
            if self._consume_task:
                await self._consume_task
            if self.consumer:
                await self.consumer.stop()
            if self.producer:
                await self.producer.stop()
            self.logger.info("Kafka client stopped")
        except Exception as e:
            self.logger.exception(f"Error during Kafka client shutdown: {e}")

    async def produce(self, key: str, value: dict) -> None:
        async def _send():
            await self.producer.send_and_wait(
                self.topic, key=key.encode(), value=json.dumps(value).encode()
            )
            self.logger.info("Message produced", extra={"key": key, "value": value})
            self.metrics.increment(KafkaMetrics.PRODUCED)

        try:
            await self.retry_policy.execute(_send)
        except Exception:
            self.logger.error(
                "Max retries reached, sending to DLQ", extra={"key": key, "value": value}
            )
            self.metrics.increment(KafkaMetrics.FAILED_PRODUCE)
            try:
                await self.send_to_dlq(key, value, "Max retries reached")
            except Exception as dlq_err:
                self.logger.exception(f"Failed to send message to DLQ: {dlq_err}")
        finally:
            self.metrics.report()

    async def send_to_dlq(self, key: str, value: dict, reason: str) -> None:
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

    async def _process_message(
        self, key: str, value: dict, callback: Callable[[str, dict], Any]
    ) -> None:
        async with self.semaphore:
            try:
                await callback(key, value)
                self.metrics.increment(KafkaMetrics.PROCESSED)
                self.logger.info("Message processed", extra={"key": key, "value": value})
            except Exception as exc:
                self.metrics.increment(KafkaMetrics.FAILED_PROCESS)
                self.logger.exception(
                    "Processing failed, sending to DLQ",
                    extra={"key": key, "value": value},
                )
                try:
                    await self.send_to_dlq(key, value, str(exc))
                except Exception as dlq_err:
                    self.logger.exception(f"Failed to send failed message to DLQ: {dlq_err}")
            finally:
                self.metrics.report()

    async def _consume_loop(self, callback: Callable[[str, dict], Any]) -> None:
        batch = []
        try:
            async for msg in self.consumer:
                if self._stop_event.is_set():
                    break

                key = msg.key.decode() if msg.key else ""
                value = json.loads(msg.value.decode())
                batch.append((key, value))

                if len(batch) >= self.batch_size:
                    await asyncio.gather(
                        *[self._process_message(k, v, callback) for k, v in batch]
                    )
                    batch.clear()

            if batch:
                await asyncio.gather(
                    *[self._process_message(k, v, callback) for k, v in batch]
                )
        except Exception as e:
            self.logger.exception(f"Error in consume loop: {e}")

    async def consume(self, callback: Callable[[str, dict], Any]) -> None:
        try:
            self._consume_task = asyncio.create_task(self._consume_loop(callback))
        except Exception as e:
            self.logger.exception(f"Failed to start consume task: {e}")
