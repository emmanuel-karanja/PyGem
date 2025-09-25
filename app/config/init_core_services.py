import asyncio
import uuid
from app.config.dependencies import (
    get_redis_client,
    get_redis_event_bus,
    get_postgres_client,
    get_kafka_client,
    get_kafka_event_bus,
)
from app.config.settings import Settings
from app.config.db_session import init_db
from app.config.logger import logger
from app.shared.event_bus.kafka_bus import KafkaEventBus
from app.shared.health import health_router

settings = Settings()

# ----------------------------
# Helper: wait for Redis
# ----------------------------
async def wait_redis(redis_client, retries=10, delay=1):
    for attempt in range(1, retries + 1):
        try:
            await redis_client.ping()
            logger.info("✅ Redis ready")
            return
        except Exception as e:
            logger.warning(f"Redis not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise RuntimeError("Redis connection failed after retries")


# ----------------------------
# Helper: wait for Kafka
# ----------------------------
async def wait_kafka(kafka_client: "AIOKafkaProducer", retries=10, delay=2):
    for attempt in range(1, retries + 1):
        try:
            await kafka_client.start()
            await kafka_client.stop()
            logger.info("✅ Kafka ready")
            return
        except Exception as e:
            logger.warning(f"Kafka not ready (attempt {attempt}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise RuntimeError("Kafka connection failed after retries")


# ----------------------------
# Helper: test event bus
# ----------------------------
async def test_event_bus(bus, event_name: str, payload: dict):
    fut = asyncio.get_event_loop().create_future()

    async def callback(msg):
        logger.info(f"Received test message on {event_name}: {msg}")
        if not fut.done():
            fut.set_result(True)

    await bus.subscribe(event_name, callback)
    await bus.publish(event_name, payload)

    try:
        await asyncio.wait_for(fut, timeout=5)
        logger.info(f"✅ Event bus '{bus.__class__.__name__}' test succeeded")
    except asyncio.TimeoutError:
        logger.error(f"❌ Event bus '{bus.__class__.__name__}' test failed: message not received")


# ----------------------------
# Core initialization
# ----------------------------
async def init_core_services():
    # Clients and buses
    redis_client = get_redis_client()
    redis_event_bus = get_redis_event_bus()
    postgres_client = get_postgres_client()
    kafka_client = get_kafka_client()
    kafka_event_bus = get_kafka_event_bus()

    # ----------------------------
    # Wait for external services
    # ----------------------------
    await wait_redis(redis_client)
    await wait_kafka(kafka_client)

    # Initialize DB
    await init_db(
        settings.postgres.get_database_url(settings.app.env_mode, for_asyncpg=False),
        app_path="app"
    )
    logger.info("✅ Postgres DB initialized")
    await postgres_client.start()

    # Start event buses
    await redis_event_bus.start()
    await kafka_event_bus.start()

    # Simple test event
    test_payload = {"id": str(uuid.uuid4()), "message": "test"}
    await asyncio.gather(
        test_event_bus(redis_event_bus, "feature_events", test_payload),
        test_event_bus(kafka_event_bus, "feature_events", test_payload)
    )

    return redis_client, redis_event_bus, postgres_client, kafka_client, kafka_event_bus
