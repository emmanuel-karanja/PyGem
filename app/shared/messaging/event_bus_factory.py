import asyncio
import os
import yaml
import configparser
from typing import Dict, Any

from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.clients import RedisClient, KafkaClient
from app.shared.annotations import ApplicationScoped, get_subscribe_registry

@ApplicationScoped
class EventBusFactory:
    """Factory for creating EventBus instances based on configuration."""

    _event_bus: Any = None

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load messaging configuration from YAML or Properties files."""
        logger = JohnWickLogger("EventBusFactory")
        config: Dict[str, Any] = {}

        if os.path.exists("messaging.eventbus.yml"):
            with open("messaging.eventbus.yml", "r") as f:
                config = yaml.safe_load(f) or {}
            logger.info("Loaded messaging config from YAML")
        elif os.path.exists("messaging.eventbus.properties"):
            parser = configparser.ConfigParser()
            parser.read("messaging.eventbus.properties")
            config = {section: dict(parser.items(section)) for section in parser.sections()}
            logger.info("Loaded messaging config from Properties")
        else:
            logger.warning("No messaging config file found, defaulting to InMemoryEventBus")

        return config

    @classmethod
    def create_event_bus(cls) -> Any:
        """Return a singleton EventBus instance based on configuration."""
        if cls._event_bus:
            return cls._event_bus

        config = cls.load_config()
        logger = JohnWickLogger("EventBusFactory")
        metrics = MetricsCollector(logger)

        transport = (
            config.get("messaging", {}).get("eventbus", {}).get("transport", "memory")
        ).lower()

        # --- Transport selection ---
        if transport == "redis":
            from app.shared.messaging.transports.redis_bus import RedisEventBus
            redis_cfg = config.get("redis", {})
            redis_url = f"redis://{redis_cfg.get('host', '127.0.0.1')}:{int(redis_cfg.get('port', 6379))}/{int(redis_cfg.get('db', 0))}"
            redis_client = RedisClient(redis_url=redis_url)
            cls._event_bus = RedisEventBus(redis_client=redis_client, logger=logger, metrics=metrics)

        elif transport == "kafka":
            from app.shared.messaging.transports.kafka_bus import KafkaEventBus
            kafka_cfg = config.get("kafka", {})
            kafka_client = KafkaClient(
                bootstrap_servers=kafka_cfg.get("bootstrap_servers", "127.0.0.1:9092"),
                group_id=kafka_cfg.get("group_id", "default-group"),
                topics=[kafka_cfg.get("topic", "default-topic")],
                dlq_topic=kafka_cfg.get("dlq_topic", "default-dlq"),
                max_concurrency=int(kafka_cfg.get("max_concurrency", 5))
            )
            cls._event_bus = KafkaEventBus(kafka_client=kafka_client, logger=logger, metrics=metrics)

        else:
            from app.shared.messaging.transports.in_process_eventbus import InProcessEventBus
            logger.info("Using InMemoryEventBus as fallback")
            cls._event_bus = InProcessEventBus(logger=logger, metrics=metrics)

        # --- Auto-bind annotated subscribers ---
        cls._bind_annotated_subscribers(cls._event_bus)
        return cls._event_bus

    @classmethod
    def _bind_annotated_subscribers(cls, event_bus: Any):
        """Register all functions decorated with @Subscribe to the EventBus."""
        registry: Dict[str, list] = get_subscribe_registry()
        for event_name, callbacks in registry.items():
            for callback in callbacks:
                # Ensure we await async subscribe
                if hasattr(event_bus.subscribe, "__call__"):
                    asyncio.create_task(event_bus.subscribe(event_name, callback))
