from app.config.logger import JohnWickLogger, get_logger as base_get_logger
from app.shared.clients import RedisClient
from app.shared.clients import KafkaClient
from app.shared.event_bus import KafkaEventBus
from app.shared.event_bus import RedisEventBus
from app.config.settings import Settings
from app.shared.metrics.metrics_collector import MetricsCollector

settings = Settings()

# ----------------------------
# Logger factory
# ----------------------------
def get_logger(name: str = "app") -> JohnWickLogger:
    return JohnWickLogger(
        name=name,
        log_file=settings.log_file,
        level=settings.log_level
    )

# ----------------------------
# Redis client factory
# ----------------------------
def get_redis_client(logger: JohnWickLogger = None) -> RedisClient:
    logger = logger or get_logger("redis_client")
    logger.info(f"Redis URL: {settings.redis_url}")
    return RedisClient(
        redis_url=settings.redis_url,
        max_retries=settings.redis_max_retries,
        retry_backoff=settings.redis_retry_backoff,
        logger=logger
    )

# ----------------------------
# Kafka client factory
# ----------------------------
def get_kafka_client(logger: JohnWickLogger = None):
    """
    Returns a KafkaClient instance (producer + consumer, metrics, DLQ, etc.)
    """
    logger = logger or get_logger("kafka_client")

    return KafkaClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_default_topic,
        dlq_topic=settings.kafka_dlq_topic,
        group_id=settings.kafka_group_id,
        logger=logger,
        max_concurrency=settings.kafka_max_concurrency,
        batch_size=settings.kafka_batch_size,
    )

# ----------------------------
# Kafka EventBus factory
# ----------------------------
def get_kafka_event_bus(logger: JohnWickLogger = None) -> KafkaEventBus:
    """
    Returns a KafkaEventBus that wraps a KafkaClient internally.
    """
    logger = logger or get_logger("kafka_event_bus")
    metrics = MetricsCollector(logger=logger)
    kafka_client = get_kafka_client(logger=logger)
    return KafkaEventBus(
        kafka_client=kafka_client,
        logger=logger,
        metrics=metrics
    )

# ----------------------------
# Redis EventBus factory (optional)
# ----------------------------
def get_redis_event_bus(logger: JohnWickLogger = None) -> RedisEventBus:
    logger = logger or get_logger("redis_event_bus")
    metrics = MetricsCollector(logger=logger)
    redis_client = get_redis_client(logger=logger)
    return RedisEventBus(
        redis_client=redis_client,
        logger=logger,
        metrics=metrics
    )
