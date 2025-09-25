from app.shared.logger import BulletproofLogger
from app.shared.clients.redis_client import RedisClient
from app.shared.clients import KafkaEventBus
from app.config.settings import Settings

settings = Settings()

# ----------------------------
# Logger factory
# ----------------------------
def get_logger(name: str = "app") -> BulletproofLogger:
    return BulletproofLogger(
        name=name,
        log_file=settings.log_file,
        level=settings.log_level
    )

# ----------------------------
# Redis client factory
# ----------------------------
def get_redis_client(logger: BulletproofLogger = None) -> RedisClient:
    logger = logger or get_logger("redis_client")
    return RedisClient(redis_url=settings.redis_url, logger=logger)

# ----------------------------
# Kafka EventBus factory
# ----------------------------
def get_kafka_event_bus(logger: BulletproofLogger = None) -> KafkaEventBus:
    logger = logger or get_logger("kafka_event_bus")
    return KafkaEventBus(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic,
        dlq_topic=settings.kafka_dlq_topic,
        group_id=settings.kafka_group_id,
        logger=logger
    )
