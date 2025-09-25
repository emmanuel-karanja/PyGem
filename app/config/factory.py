from functools import lru_cache
from app.config.logger import JohnWickLogger, get_logger
from app.shared.clients import RedisClient, KafkaClient, PostgresClient
from app.shared.event_bus import KafkaEventBus, RedisEventBus
from app.shared.metrics.metrics_collector import MetricsCollector
from app.config.settings import Settings
from app.shared.retry import ExponentialBackoffRetry

settings = Settings()

# ----------------------------
# Redis client factory
# ----------------------------
@lru_cache
def get_redis_client() -> RedisClient:
    logger = get_logger("redis_client")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.redis_max_retries,
        base_delay=settings.redis_retry_backoff
    )
    return RedisClient(
        redis_url=settings.redis_url,
        logger=logger,
        retry_policy=retry_policy
    )

# ----------------------------
# Postgres client factory
# ----------------------------
@lru_cache
def get_postgres_client() -> PostgresClient:
    logger = get_logger("postgres_client")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.db_max_retries,
        base_delay=settings.db_retry_backoff
    )
    return PostgresClient(
        dsn=settings.db_dsn,
        logger=logger,
        retry_policy=retry_policy
    )

# ----------------------------
# Kafka client factory
# ----------------------------
@lru_cache
def get_kafka_client() -> KafkaClient:
    logger = get_logger("kafka_client")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.kafka_max_retries,
        base_delay=settings.kafka_retry_backoff
    )
    return KafkaClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_default_topic,
        dlq_topic=settings.kafka_dlq_topic,
        group_id=settings.kafka_group_id,
        logger=logger,
        retry_policy=retry_policy,
        max_concurrency=settings.kafka_max_concurrency,
        batch_size=settings.kafka_batch_size,
    )

# ----------------------------
# Redis EventBus factory
# ----------------------------
@lru_cache
def get_redis_event_bus() -> RedisEventBus:
    logger = get_logger("redis_event_bus")
    metrics = MetricsCollector(logger=logger)
    return RedisEventBus(
        redis_client=get_redis_client(),
        logger=logger,
        retry_policy=ExponentialBackoffRetry(
        max_retries=settings.redis_max_retries,
        base_delay=settings.redis_retry_backoff),
        metrics=metrics
    )

# ----------------------------
# Kafka EventBus factory
# ----------------------------
@lru_cache
def get_kafka_event_bus() -> KafkaEventBus:
    logger = get_logger("kafka_event_bus")
    metrics = MetricsCollector(logger=logger)
    return KafkaEventBus(
        kafka_client=get_kafka_client(),
        logger=logger,
        metrics=metrics,
        retry_policy = ExponentialBackoffRetry(
        max_retries=settings.kafka_max_retries,
        base_delay=settings.kafka_retry_backoff
    )
    )
