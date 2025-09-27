import asyncio
import os
import yaml
import configparser
from typing import Dict, Any

from app.shared.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector
from app.shared.clients import RedisClient, KafkaClient
from app.shared.annotations.core import ApplicationScoped
from app.shared.registry import _CONSUMER_REGISTRY, _PRODUCER_REGISTRY, _SINGLETONS


@ApplicationScoped
class EventBusFactory:
    """Factory for creating and wiring EventBus instances."""

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
            logger.info(f"Created RedisEventBus instance with URL {redis_url}")

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
            logger.info(f"Created KafkaEventBus instance with bootstrap_servers={kafka_cfg.get('bootstrap_servers')}")

        else:
            from app.shared.messaging.transports.in_process_eventbus import InProcessEventBus
            cls._event_bus = InProcessEventBus(logger=logger, metrics=metrics)
            logger.info("Created InMemoryEventBus instance as fallback")

        return cls._event_bus

    @classmethod
    def bootstrap(cls):
        """Bind producers and consumers to the EventBus."""
        event_bus = cls.create_event_bus()
        logger = JohnWickLogger("EventBusFactory")

        logger.info("Bootstrapping producers and consumers...")

        # --- Wire producers ---
        for producer_cls in _PRODUCER_REGISTRY:
            instance = _SINGLETONS.get(producer_cls)
            if not instance:
                instance = producer_cls()
                _SINGLETONS[producer_cls] = instance
            instance.event_bus = event_bus
            logger.info(f"Bound producer {producer_cls.__name__} to EventBus")

        # --- Wire consumers ---
        for topic, cls_type, method_name in _CONSUMER_REGISTRY:
            if not cls_type:
                logger.warning(f"Skipping consumer {method_name} — no class resolved")
                continue

            instance = _SINGLETONS.get(cls_type)
            if not instance:
                instance = cls_type()
                _SINGLETONS[cls_type] = instance

            method = getattr(instance, method_name, None)
            if method:
                event_bus.subscribe(topic, method)
                logger.info(f"Registered consumer {cls_type.__name__}.{method_name} for topic {topic}")
            else:
                logger.warning(f"Consumer method {method_name} not found on {cls_type.__name__}")

        logger.info("EventBusFactory bootstrap complete ")
        return event_bus
