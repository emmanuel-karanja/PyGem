import os
import yaml
import configparser
import asyncio
from typing import Optional, Dict

from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.clients import RedisClient, KafkaClient
from app.shared.annotations import ApplicationScoped, get_subscribe_registry

@ApplicationScoped
class EventBusFactory:
    _event_bus = None

    @staticmethod
    def load_config() -> dict:
        """Load config from messaging.eventbus.yml or .properties"""
        logger = JohnWickLogger("EventBusFactory")
        config = {}

        if os.path.exists("messaging.eventbus.yml"):
            with open("messaging.eventbus.yml", "r") as f:
                config = yaml.safe_load(f) or {}
            logger.info("Loaded messaging config from YAML")
        elif os.path.exists("messaging.eventbus.properties"):
            parser = configparser.ConfigParser()
            parser.read("messaging.eventbus.properties")
            config = {s: dict(parser.items(s)) for s in parser.sections()}
            logger.info("Loaded messaging config from Properties")
        else:
            logger.warning("No messaging config file found, defaulting to InMemoryEventBus")

        return config

    @classmethod
    def create_event_bus(cls) -> object:
        if cls._event_bus:
            return cls._event_bus

        config = cls.load_config()
        logger = JohnWickLogger("EventBusFactory")
        metrics = MetricsCollector(logger)

        transport = (
            config.get("messaging", {})
            .get("eventbus", {})
            .get("transport", "memory")
        ).lower()

        # Local imports to avoid circular imports
        if transport == "redis":
            from app.shared.messaging.transports.redis_bus import RedisEventBus

            redis_config = config.get("redis", {})
            redis_client = RedisClient(
                host=redis_config.get("host", "127.0.0.1"),
                port=int(redis_config.get("port", 6379)),
                db=int(redis_config.get("db", 0)),
            )
            cls._event_bus = RedisEventBus(redis_client=redis_client, logger=logger, metrics=metrics)

        elif transport == "kafka":
            from app.shared.messaging.transports.kafka_bus import KafkaEventBus

            kafka_config = config.get("kafka", {})
            kafka_client = KafkaClient(
                bootstrap_servers=kafka_config.get("bootstrap_servers", "127.0.0.1:9092"),
                group_id=kafka_config.get("group_id", "default-group"),
                topic=kafka_config.get("topic", "default-topic"),
               dlq_topic=kafka_config.get("dlq_topic", "default-dlq")
            )
            cls._event_bus = KafkaEventBus(kafka_client=kafka_client, logger=logger, metrics=metrics)

        else:
            from app.shared.messaging.transports.in_process_eventbus import InProcessEventBus
            logger.info("Using InMemoryEventBus as fallback")
            cls._event_bus = InProcessEventBus(logger=logger, metrics=metrics)

        # Auto-bind annotated subscribers
        cls._bind_annotated_subscribers(cls._event_bus)

        return cls._event_bus

    @classmethod
    def _bind_annotated_subscribers(cls, event_bus):
        """
        Registers all functions decorated with @Subscribe to the EventBus.
        """
        registry: Dict[str, list] = get_subscribe_registry()
        for event_name, callbacks in registry.items():
            for callback in callbacks:
                event_bus.subscribe(event_name, callback)
