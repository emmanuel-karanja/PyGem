from app.config.logger import JohnWickLogger, get_logger
from app.shared.clients.redis_client import RedisClient
from app.shared.event_bus.kafka_bus import KafkaEventBus
from app.shared.event_bus.redis_bus import RedisEventBus
from app.config.settings import Settings

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
    return RedisClient(redis_url=settings.redis_url, logger=logger)

# ----------------------------
# Kafka EventBus factory
# ----------------------------
def get_kafka_event_bus(logger: JohnWickLogger = None) -> KafkaEventBus:
    logger = logger or get_logger("kafka_event_bus")
    return KafkaEventBus(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        dlq_topic=settings.kafka_dlq_topic,  # pass DLQ topic here
        max_retries=5,
        logger=logger
    )

# ----------------------------
# Redis EventBus factory (optional)
# ----------------------------
def get_redis_event_bus(logger: JohnWickLogger = None) -> RedisEventBus:
    logger = logger or get_logger("redis_event_bus")
    return RedisEventBus(logger=logger)
