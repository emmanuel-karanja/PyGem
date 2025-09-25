from contextlib import asynccontextmanager
from fastapi import FastAPI
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
from app.shared.health import health_router
import asyncio
import uuid

settings = Settings()


async def wait_with_retry(name: str, coro_func, retry_policy, *args, **kwargs):
    """
    Wait for a service to be ready using a RetryPolicy.
    """
    async def _attempt():
        await coro_func(*args, **kwargs)

    try:
        await retry_policy.execute(_attempt)
        logger.info(f"✅ {name} ready")
    except Exception as e:
        logger.error(f"❌ {name} failed to start: {e}")
        raise


async def test_event_bus(bus, test_event: str, payload: dict):
    """
    Simple test: publish a message and subscribe to receive it once.
    """
    fut = asyncio.get_event_loop().create_future()

    async def callback(msg):
        logger.info(f"Received test message on {test_event}: {msg}")
        if not fut.done():
            fut.set_result(True)

    # Subscribe to test event
    await bus.subscribe(test_event, callback)

    # Publish test message
    await bus.publish(test_event, payload)

    try:
        await asyncio.wait_for(fut, timeout=5)
        logger.info(f"✅ Event bus '{bus.__class__.__name__}' test succeeded for event '{test_event}'")
    except asyncio.TimeoutError:
        logger.error(f"❌ Event bus '{bus.__class__.__name__}' test failed: message not received")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application...")

    # Initialize clients and buses from factories
    redis_client = get_redis_client()
    redis_event_bus = get_redis_event_bus()
    postgres_client = get_postgres_client()
    kafka_client = get_kafka_client()
    kafka_event_bus = get_kafka_event_bus()

    # ----------------------------
    # Wait for services with retries
    # ----------------------------
    await wait_with_retry("Redis client", redis_client.connect, redis_client.retry_policy)
    await wait_with_retry("Redis event bus", redis_event_bus.start, redis_event_bus.retry_policy)
    await wait_with_retry("Kafka client", kafka_client.start, kafka_client.retry_policy)
    await wait_with_retry("Kafka event bus", kafka_event_bus.start, kafka_event_bus.retry_policy)
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")
    await wait_with_retry("PostgresClient", postgres_client.start, postgres_client.retry_policy)

    # ----------------------------
    # Event Bus tests
    # ----------------------------
    test_payload = {"id": str(uuid.uuid4()), "message": "test"}
    await test_event_bus(redis_event_bus, "feature_events", test_payload)
    await test_event_bus(kafka_event_bus, "feature_events", test_payload)

    logger.info("🎉 Application startup complete")
    yield

    # ----------------------------
    # Shutdown
    # ----------------------------
    logger.info("⚠️ Shutting down application...")
    await postgres_client.stop()
    await kafka_event_bus.stop()
    await redis_event_bus.stop()
    await kafka_client.stop()
    await redis_client.close()
    logger.info("🎯 Application shutdown complete")


# Create FastAPI app
app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)
app.include_router(health_router)
logger.info("✅ Health routes initialized")
