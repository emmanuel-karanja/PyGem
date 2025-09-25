# my_event_system/event_bus/kafka_bus.py
import asyncio
import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from typing import Callable, Dict, List
from .base import EventBus
from logging import Logger

class KafkaEventBus(EventBus):
    def __init__(
        self,
        bootstrap_servers: str,
        logger: Logger,
        group_id: str = "eventbus-group",
        max_retries: int = 5
    ):
        self.bootstrap_servers = bootstrap_servers
        self.logger = logger
        self.group_id = group_id
        self.max_retries = max_retries

        self.producer: AIOKafkaProducer | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.subscribers: Dict[str, List[Callable]] = {}

    async def start(self):
        """Start Kafka producer"""
        self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self.producer.start()
        self.logger.info("KafkaEventBus producer started")

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        self.logger.info("KafkaEventBus stopped")

    async def publish(self, event_name: str, payload: dict):
        """Publish an event to Kafka"""
        if not self.producer:
            await self.start()
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.producer.send_and_wait(
                    topic=event_name,
                    key=None,
                    value=json.dumps(payload).encode()
                )
                self.logger.info("Event published", extra={"event": event_name, "payload": payload})
                return
            except Exception as exc:
                self.logger.warning(f"Publish attempt {attempt} failed", extra={"error": str(exc)})
                await asyncio.sleep(0.5 * attempt)
        self.logger.error("Failed to publish event after max retries", extra={"event": event_name, "payload": payload})

    async def subscribe(self, event_name: str, callback: Callable):
        """Subscribe to a Kafka topic"""
        self.consumer = AIOKafkaConsumer(
            event_name,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="earliest"
        )
        await self.consumer.start()
        self.subscribers.setdefault(event_name, []).append(callback)
        self.logger.info("Subscribed to Kafka topic", extra={"topic": event_name})

        async def consume_loop():
            async for msg in self.consumer:
                payload = json.loads(msg.value.decode())
                for cb in self.subscribers[event_name]:
                    asyncio.create_task(cb(payload))

        asyncio.create_task(consume_loop())
