from functools import lru_cache
from app.config.logger import JohnWickLogger, get_logger
from app.shared.clients import RedisClient, KafkaClient
from app.shared.database import PostgresClient
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
    logger = JohnWickLogger(name="RedisClient")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.redis.max_retries,
        base_delay=settings.redis.retry_backoff
    )
    return RedisClient(
        redis_url=settings.redis.get_url(settings.app.env_mode),
        logger=logger,
        retry_policy=retry_policy
    )


# ----------------------------
# Postgres client factory
# ----------------------------
@lru_cache
def get_postgres_client() -> PostgresClient:
    logger = JohnWickLogger(name="PostgresClient")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.postgres.max_retries,
        base_delay=settings.postgres.retry_backoff
    )
    return PostgresClient(
        dsn=settings.postgres.get_database_url(env_mode=settings.app.env_mode,for_asyncpg=True),
        logger=logger,
        retry_policy=retry_policy
    )


# ----------------------------
# Kafka client factory
# ----------------------------
@lru_cache
def get_kafka_client() -> KafkaClient:
    logger = JohnWickLogger(name="RedisEventBus")
    retry_policy = ExponentialBackoffRetry(
        max_retries=settings.kafka.max_retries,
        base_delay=settings.kafka.retry_backoff
    )
    return KafkaClient(
        bootstrap_servers=settings.kafka.get_bootstrap_servers(settings.app.env_mode),
        topic=settings.kafka.default_topic,
        dlq_topic=settings.kafka.dlq_topic,
        group_id=settings.kafka.group_id,
        logger=logger,
        retry_policy=retry_policy,
        max_concurrency=settings.kafka.max_concurrency,
        batch_size=settings.kafka.batch_size,
    )


# ----------------------------
# Redis EventBus factory
# ----------------------------
@lru_cache
def get_redis_event_bus() -> RedisEventBus:
    logger = JohnWickLogger(name="RedisEventBus")
    metrics = MetricsCollector(logger=logger)
    return RedisEventBus(
        redis_client=get_redis_client(),
        logger=logger,
        retry_policy=ExponentialBackoffRetry(
            max_retries=settings.redis.max_retries,
            base_delay=settings.redis.retry_backoff
        ),
        metrics=metrics
    )


# ----------------------------
# Kafka EventBus factory
# ----------------------------
@lru_cache
def get_kafka_event_bus() -> KafkaEventBus:
    logger = JohnWickLogger(name="KafkaEventBus")
    metrics = MetricsCollector(logger=logger)
    return KafkaEventBus(
        kafka_client=get_kafka_client(),
        logger=logger,
        metrics=metrics,
        retry_policy=ExponentialBackoffRetry(
            max_retries=settings.kafka.max_retries,
            base_delay=settings.kafka.retry_backoff
        )
    )
